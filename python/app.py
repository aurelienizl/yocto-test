import datetime
import signal
import sys
import time
import shutil
import psutil                 # <-- newly added

from flask import (
    Flask,
    request,
    render_template,
    jsonify,
    Response,
    stream_with_context,
    send_file,
)
from db import db
from job_queue import job_queue, Job

app = Flask(__name__, template_folder="templates", static_folder="static")


def _shutdown_handler(signum, frame):
    print(
        f"[{datetime.datetime.utcnow().isoformat()}] Shutdown signal {signum}",
        file=sys.stderr,
    )
    job_queue.shutdown()
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown_handler)
signal.signal(signal.SIGTERM, _shutdown_handler)


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/repos")
def repos():
    return render_template("repos.html")


@app.route("/enqueue", methods=["POST"])
def enqueue():
    git_uri = request.form.get("git_uri", "").strip()
    if not git_uri:
        return jsonify({"error": "No Git URI provided"}), 400
    job = job_queue.add_job(Job(git_uri))
    return jsonify({"message": "Job enqueued", "job_id": job.id})


@app.route("/tasks", methods=["GET"])
def list_tasks():
    tasks = db.get_tasks()
    return jsonify(tasks)


@app.route("/kill", methods=["POST"])
def kill_job():
    success, msg = job_queue.kill_current_job()
    return (
        (jsonify({"message": msg}), 200) if success else (jsonify({"error": msg}), 400)
    )


@app.route("/remove", methods=["POST"])
def remove_job():
    job_id = request.form.get("job_id", "").strip()
    if not job_id:
        return jsonify({"error": "No job ID provided"}), 400
    success, msg = job_queue.remove_job(job_id)
    return (
        (jsonify({"message": msg}), 200) if success else (jsonify({"error": msg}), 400)
    )


@app.route("/logs_json/<job_id>")
def logs_json(job_id):
    after_id = request.args.get("after_id", default=0, type=int)
    rows = db.get_logs_since(job_id, after_id)
    return jsonify(rows)


@app.route("/metrics/cpu")
def metrics_cpu():
    """
    Returns current overall CPU usage percentage.
    """
    # non-blocking instantaneous reading
    percent = psutil.cpu_percent(interval=None)
    return jsonify({"cpu_percent": percent})


@app.route("/metrics/memory")
def metrics_memory():
    """
    Returns total/available memory and usage percent.
    """
    m = psutil.virtual_memory()
    return jsonify({
        "total":     m.total,
        "available": m.available,
        "percent":   m.percent
    })


@app.route("/metrics/disk")
def metrics_disk():
    """
    Returns root-filesystem disk usage.
    """
    du = shutil.disk_usage("/")
    percent = round(du.used / du.total * 100, 1)
    return jsonify({
        "total":   du.total,
        "used":    du.used,
        "free":    du.free,
        "percent": percent
    })


@app.route("/tasks/<job_id>/download")
def download_content(job_id):
    task = db.get_task(job_id)
    if not task or not task["has_content"]:
        return jsonify({"error": "No content available"}), 404

    headers = {"Content-Disposition": f'attachment; filename="{job_id}.zip"'}
    return Response(
        db.stream_task_content(job_id),
        mimetype="application/zip",
        headers=headers
    )


@app.route("/current")
def current_job():
    cj = job_queue.current_job
    if cj:
        return jsonify({"id": cj.id, "git_uri": cj.git_uri, "status": cj.status})
    return jsonify({"message": "No job is currently running."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
