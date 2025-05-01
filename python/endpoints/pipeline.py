from flask import Blueprint, request, jsonify, Response
from job_queue import job_queue, Job
from db import db

pipeline_bp = Blueprint("pipeline", __name__)

@pipeline_bp.route("/enqueue", methods=["POST"])
def enqueue():
    git_uri = request.form.get("git_uri", "").strip()
    if not git_uri:
        return jsonify({"error": "No Git URI provided"}), 400
    job = job_queue.add_job(Job(git_uri))
    return jsonify({"message": "Job enqueued", "job_id": job.id})

@pipeline_bp.route("/tasks", methods=["GET"])
def list_tasks():
    tasks = db.get_tasks()
    return jsonify(tasks)

@pipeline_bp.route("/kill", methods=["POST"])
def kill_job():
    success, msg = job_queue.kill_current_job()
    return (
        (jsonify({"message": msg}), 200) if success else (jsonify({"error": msg}), 400)
    )

@pipeline_bp.route("/remove", methods=["POST"])
def remove_job():
    job_id = request.form.get("job_id", "").strip()
    if not job_id:
        return jsonify({"error": "No job ID provided"}), 400
    success, msg = job_queue.remove_job(job_id)
    return (
        (jsonify({"message": msg}), 200) if success else (jsonify({"error": msg}), 400)
    )

@pipeline_bp.route("/logs_json/<job_id>")
def logs_json(job_id):
    after_id = request.args.get("after_id", default=0, type=int)
    rows = db.get_logs_since(job_id, after_id)
    return jsonify(rows)

@pipeline_bp.route("/tasks/<job_id>/download")
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

@pipeline_bp.route("/current")
def current_job():
    cj = job_queue.current_job
    if cj:
        return jsonify({"id": cj.id, "git_uri": cj.git_uri, "status": cj.status})
    return jsonify({"message": "No job is currently running."})
