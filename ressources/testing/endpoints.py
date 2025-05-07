import os
from flask import Blueprint, request, send_from_directory, jsonify, current_app
from werkzeug.utils import secure_filename
import shutil

def create_endpoints(app, base_dir):
    bp = Blueprint('api', __name__, url_prefix='/api')

    def success(data=None, message='Success'):
        return jsonify({'status': 'success', 'message': message, 'data': data})

    def error(message='Error', code=400):
        resp = jsonify({'status': 'error', 'message': message, 'data': None})
        resp.status_code = code
        return resp

    def resolve(path):
        # Prevent directory traversal
        target = os.path.abspath(os.path.join(base_dir, path))
        if not target.startswith(os.path.abspath(base_dir)):
            raise PermissionError('Invalid path')
        return target

    @bp.route('/list')
    def list_files():
        path = request.args.get('path', '')
        try:
            full = resolve(path)
            items = []
            for name in os.listdir(full):
                p = os.path.join(full, name)
                st = os.stat(p)
                items.append({
                    'name': name,
                    'is_dir': os.path.isdir(p),
                    'size': st.st_size,
                    'last_modified': st.st_mtime
                })
            return success(items)
        except PermissionError as e:
            return error(str(e), 403)
        except Exception as e:
            current_app.logger.exception(e)
            return error(str(e), 500)

    @bp.route('/download')
    def download():
        path = request.args.get('path', '')
        name = request.args.get('name')
        if not name:
            return error('Missing name')
        try:
            folder = resolve(path)
            return send_from_directory(folder, name, as_attachment=True)
        except PermissionError as e:
            return error(str(e), 403)
        except Exception as e:
            current_app.logger.exception(e)
            return error(str(e), 500)

    @bp.route('/delete', methods=['POST'])
    def delete():
        data = request.get_json() or dict(request.form)
        path = data.get('path', '')
        name = data.get('name')
        if not name:
            return error('Missing name')
        try:
            full = os.path.join(resolve(path), name)
            if os.path.isdir(full):
                os.rmdir(full)
            else:
                os.remove(full)
            return success(message=f'"{name}" deleted')
        except PermissionError as e:
            return error(str(e), 403)
        except OSError as e:
            return error(str(e), 400)
        except Exception as e:
            current_app.logger.exception(e)
            return error(str(e), 500)

    @bp.route('/upload', methods=['POST'])
    def upload():
        path = request.form.get('path', '')
        file = request.files.get('file')
        if not file:
            return error('No file provided')
        try:
            folder = resolve(path)
            filename = secure_filename(file.filename)
            file.save(os.path.join(folder, filename))
            return success({'filename': filename}, f'"{filename}" uploaded')
        except PermissionError as e:
            return error(str(e), 403)
        except Exception as e:
            current_app.logger.exception(e)
            return error(str(e), 500)

    @bp.route('/create-folder', methods=['POST'])
    def create_folder():
        data = request.get_json() or dict(request.form)
        path = data.get('path', '')
        name = data.get('name')
        if not name:
            return error('Missing folder name')
        try:
            folder = resolve(path)
            new_folder = os.path.join(folder, secure_filename(name))
            os.makedirs(new_folder)
            return success(message=f'Folder "{name}" created')
        except FileExistsError:
            return error('Folder already exists', 409)
        except PermissionError as e:
            return error(str(e), 403)
        except Exception as e:
            current_app.logger.exception(e)
            return error(str(e), 500)

    @bp.route('/rename', methods=['POST'])
    def rename():
        data = request.get_json() or dict(request.form)
        path = data.get('path', '')
        old = data.get('old')
        new = data.get('new')
        if not old or not new:
            return error('Missing old or new name')
        try:
            folder = resolve(path)
            os.rename(
                os.path.join(folder, old),
                os.path.join(folder, secure_filename(new))
            )
            return success(message=f'"{old}" → "{new}"')
        except PermissionError as e:
            return error(str(e), 403)
        except Exception as e:
            current_app.logger.exception(e)
            return error(str(e), 500)

    @bp.route('/move', methods=['POST'])
    def move():
        data = request.get_json() or dict(request.form)
        path   = data.get('path', '')
        name   = data.get('name')
        target = data.get('target')
        if not name or target is None:
            return error('Missing name or target', 400)
        try:
            src = os.path.join(resolve(path), name)
            dest_dir = resolve(target)
            if not os.path.isdir(dest_dir):
                return error(f'"{target}" is not a directory', 400)
            dst = os.path.join(dest_dir, name)
            os.rename(src, dst)
            return success(message=f'"{name}" moved to "{target}"')
        except PermissionError as e:
            return error(str(e), 403)
        except Exception as e:
            current_app.logger.exception(e)
            return error(str(e), 500)
        
    @bp.route('/copy', methods=['POST'])
    def copy_item():
        data   = request.get_json() or dict(request.form)
        path   = data.get('path', '')
        name   = data.get('name')
        target = data.get('target', '')
        if not name or not target:
            return error('Missing name or target', 400)

        try:
            src_dir   = resolve(path)
            dst_dir   = resolve(target)

            # Build full source path and re‐resolve to ensure safety
            raw_src = os.path.abspath(os.path.join(src_dir, name))
            if not raw_src.startswith(os.path.abspath(base_dir)):
                raise PermissionError('Invalid source path')
            if not os.path.exists(raw_src):
                return error('Source does not exist', 404)

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
            return error('Destination already exists', 409)
        except Exception as e:
            current_app.logger.exception(e)
            return error(str(e), 500)



    app.register_blueprint(bp)
