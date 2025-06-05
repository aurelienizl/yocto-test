import os
import shutil
from flask import Blueprint, request, send_from_directory, jsonify, current_app
from werkzeug.utils import secure_filename

mirror_bp = Blueprint("mirror", __name__, url_prefix="/mirror")

src_dir = "/home/generic/yocto-mirror"


# —————————————————————————————————————————————————————————————
# Helpers: uniform success/error JSON responses
# —————————————————————————————————————————————————————————————
def success(data=None, message="Success"):
    return jsonify({"status": "success", "message": message, "data": data})


def error(message="Error", code=400):
    resp = jsonify({"status": "error", "message": message, "data": None})
    resp.status_code = code
    return resp


def resolve(path: str) -> str:
    """
    Safely resolve `path` under base_dir. Prevents directory traversal.
    """
    base_dir = src_dir
    if not base_dir:
        raise RuntimeError("src_dir not configured")
    # Compute absolute paths
    full = os.path.abspath(os.path.join(base_dir, path or ""))
    if not full.startswith(os.path.abspath(base_dir)):
        raise PermissionError("Invalid path")
    return full


# —————————————————————————————————————————————————————————————
# Endpoint: List directory contents
# GET /mirror/list?path=<relative-path>
# —————————————————————————————————————————————————————————————
@mirror_bp.route("/list", methods=["GET"])
def list_files():
    path = request.args.get("path", "")
    try:
        full = resolve(path)
        items = []
        for name in os.listdir(full):
            p = os.path.join(full, name)
            st = os.stat(p)
            items.append(
                {
                    "name": name,
                    "is_dir": os.path.isdir(p),
                    "size": st.st_size,
                    "last_modified": int(st.st_mtime),
                }
            )
        return success(items)
    except PermissionError as e:
        return error(str(e), 403)
    except FileNotFoundError:
        return error("Directory not found", 404)
    except Exception as e:
        current_app.logger.exception(e)
        return error(str(e), 500)


# —————————————————————————————————————————————————————————————
# Endpoint: Download a file
# GET /mirror/download?path=<relative-dir>&name=<filename>
# —————————————————————————————————————————————————————————————
@mirror_bp.route("/download", methods=["GET"])
def download():
    path = request.args.get("path", "")
    name = request.args.get("name", "").strip()
    if not name:
        return error("Missing name", 400)
    try:
        folder = resolve(path)
        return send_from_directory(folder, name, as_attachment=True)
    except PermissionError as e:
        return error(str(e), 403)
    except FileNotFoundError:
        return error("File not found", 404)
    except Exception as e:
        current_app.logger.exception(e)
        return error(str(e), 500)


# —————————————————————————————————————————————————————————————
# Endpoint: Delete a file or empty folder
# POST /mirror/delete   JSON or form: { "path": <dir>, "name": <entry> }
# —————————————————————————————————————————————————————————————
@mirror_bp.route("/delete", methods=["POST"])
def delete():
    data = request.get_json(silent=True) or request.form
    path = data.get("path", "")
    name = data.get("name", "").strip()
    if not name:
        return error("Missing name", 400)
    try:
        full = os.path.join(resolve(path), name)
        if os.path.isdir(full):
            os.rmdir(full)
        else:
            os.remove(full)
        return success(message=f'"{name}" deleted')
    except PermissionError as e:
        return error(str(e), 403)
    except FileNotFoundError:
        return error("Not found", 404)
    except OSError as e:
        # e.g. directory not empty
        return error(str(e), 400)
    except Exception as e:
        current_app.logger.exception(e)
        return error(str(e), 500)


# —————————————————————————————————————————————————————————————
# Endpoint: Upload a file
# POST /mirror/upload   form-data: "path" + file field "file"
# —————————————————————————————————————————————————————————————
@mirror_bp.route("/upload", methods=["POST"])
def upload():
    path = request.form.get("path", "")
    file = request.files.get("file")
    if not file:
        return error("No file provided", 400)
    if not file.filename:
        return error("No filename provided", 400)
    try:
        folder = resolve(path)
        filename = secure_filename(file.filename or "")
        if not filename:
            return error("Invalid filename", 400)
        file.save(os.path.join(folder, filename))
        return success({"filename": filename}, f'"{filename}" uploaded')
    except PermissionError as e:
        return error(str(e), 403)
    except Exception as e:
        current_app.logger.exception(e)
        return error(str(e), 500)


# —————————————————————————————————————————————————————————————
# Endpoint: Create a new folder
# POST /mirror/create-folder   JSON or form: { "path": <dir>, "name": <new-folder-name> }
# —————————————————————————————————————————————————————————————
@mirror_bp.route("/create-folder", methods=["POST"])
def create_folder():
    data = request.get_json(silent=True) or request.form
    path = data.get("path", "")
    name = data.get("name", "").strip()
    if not name:
        return error("Missing folder name", 400)
    try:
        folder = resolve(path)
        new_folder = os.path.join(folder, secure_filename(name))
        os.makedirs(new_folder, exist_ok=False)
        return success(message=f'Folder "{name}" created')
    except FileExistsError:
        return error("Folder already exists", 409)
    except PermissionError as e:
        return error(str(e), 403)
    except Exception as e:
        current_app.logger.exception(e)
        return error(str(e), 500)


# —————————————————————————————————————————————————————————————
# Endpoint: Rename a file or folder
# POST /mirror/rename   JSON or form: { "path": <dir>, "old": <old-name>, "new": <new-name> }
# —————————————————————————————————————————————————————————————
@mirror_bp.route("/rename", methods=["POST"])
def rename():
    data = request.get_json(silent=True) or request.form
    path = data.get("path", "")
    old = data.get("old", "").strip()
    new = data.get("new", "").strip()
    if not old or not new:
        return error("Missing old or new name", 400)
    try:
        folder = resolve(path)
        old_path = os.path.join(folder, old)
        new_path = os.path.join(folder, secure_filename(new))
        os.rename(old_path, new_path)
        return success(message=f'"{old}" → "{new}"')
    except PermissionError as e:
        return error(str(e), 403)
    except FileNotFoundError:
        return error("Item not found", 404)
    except Exception as e:
        current_app.logger.exception(e)
        return error(str(e), 500)


# —————————————————————————————————————————————————————————————
# Endpoint: Move a file or folder into another directory
# POST /mirror/move   JSON or form: { "path": <src-dir>, "name": <entry>, "target": <dst-dir> }
# —————————————————————————————————————————————————————————————
@mirror_bp.route("/move", methods=["POST"])
def move():
    data = request.get_json(silent=True) or request.form
    path = data.get("path", "")
    name = data.get("name", "").strip()
    target = data.get("target", "").strip()
    if not name or not target:
        return error("Missing name or target", 400)
    try:
        src = os.path.join(resolve(path), name)
        dst_dir = resolve(target)
        if not os.path.isdir(dst_dir):
            return error(f'"{target}" is not a directory', 400)
        dst = os.path.join(dst_dir, name)
        os.rename(src, dst)
        return success(message=f'"{name}" moved to "{target}"')
    except PermissionError as e:
        return error(str(e), 403)
    except FileNotFoundError:
        return error("Source not found", 404)
    except Exception as e:
        current_app.logger.exception(e)
        return error(str(e), 500)


# —————————————————————————————————————————————————————————————
# Endpoint: Copy a file or entire folder tree
# POST /mirror/copy   JSON or form: { "path": <src-dir>, "name": <entry>, "target": <dst-dir> }
# —————————————————————————————————————————————————————————————
@mirror_bp.route("/copy", methods=["POST"])
def copy_item():
    data = request.get_json(silent=True) or request.form
    path = data.get("path", "")
    name = data.get("name", "").strip()
    target = data.get("target", "").strip()
    if not name or not target:
        return error("Missing name or target", 400)

    try:
        src_dir = resolve(path)
        dst_dir = resolve(target)

        raw_src = os.path.abspath(os.path.join(src_dir, name))
        if not raw_src.startswith(os.path.abspath(src_dir)):
            raise PermissionError("Invalid source path")
        if not os.path.exists(raw_src):
            return error("Source does not exist", 404)

        dst_name = secure_filename(name)
        dst_path = os.path.join(dst_dir, dst_name)

        if os.path.isdir(raw_src):
            os.makedirs(dst_path, exist_ok=True)
            for entry in os.listdir(raw_src):
                s_entry = os.path.join(raw_src, entry)
                d_entry = os.path.join(dst_path, secure_filename(entry))
                if os.path.isdir(s_entry):
                    shutil.copytree(s_entry, d_entry)
                else:
                    shutil.copy2(s_entry, d_entry)
        else:
            shutil.copy2(raw_src, dst_path)

        return success(message=f'"{name}" copied to "{target}"')
    except PermissionError as e:
        return error(str(e), 403)
    except FileExistsError:
        return error("Destination already exists", 409)
    except Exception as e:
        current_app.logger.exception(e)
        return error(str(e), 500)
