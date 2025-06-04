from __future__ import annotations

from flask import Blueprint, jsonify, request, Response

from buildos_db import db
from buildos_job.queue import job_queue

pipeline_bp = Blueprint("pipeline", __name__)


# ------------------------------------------------------------------
# queue / control
# ------------------------------------------------------------------
@pipeline_bp.route("/enqueue", methods=["POST"])
def enqueue():
    repo_id = request.form.get("repo_id", "").strip()
    if not repo_id:
        return jsonify({"error": "No repository id provided"}), 400

    if not db.get_repository(repo_id):
        return jsonify({"error": "Repository not found"}), 404

    job = job_queue.enqueue(repo_id)
    return jsonify({"message": "Job enqueued", "job_id": job.id})


@pipeline_bp.route("/kill", methods=["POST"])
def kill_job():
    success, msg = job_queue.kill_current_job()
    status = 200 if success else 400
    return jsonify({"message" if success else "error": msg}), status


@pipeline_bp.route("/remove", methods=["POST"])
def remove_job():
    job_id = request.form.get("job_id", "").strip()
    if not job_id:
        return jsonify({"error": "No job ID provided"}), 400
    success, msg = job_queue.remove_job(job_id)
    status = 200 if success else 400
    return jsonify({"message" if success else "error": msg}), status


# ------------------------------------------------------------------
# inspection endpoints
# ------------------------------------------------------------------
@pipeline_bp.route("/repositories", methods=["GET"])
def list_repositories():
    return jsonify(db.get_repositories())


@pipeline_bp.route("/tasks", methods=["GET"])
def list_tasks():
    repo_id = request.args.get("repo_id")
    if repo_id:
        tasks = db.get_tasks_for_repo(repo_id)
    else:
        # collect tasks for all repos – suitable for small‑medium instance
        tasks = []
        for repo in db.get_repositories():
            tasks.extend(db.get_tasks_for_repo(repo["id"]))
    return jsonify(tasks)


@pipeline_bp.route("/logs_json/<job_id>")
def logs_json(job_id: str):
    after_id = request.args.get("after_id", default=0, type=int)
    return jsonify(db.get_logs_since(job_id, after_id))


@pipeline_bp.route("/tasks/<job_id>/download")
def download_content(job_id: str):
    task = db.get_task(job_id)
    if not task or not task["has_content"]:
        return jsonify({"error": "No content available"}), 404

    headers = {"Content-Disposition": f'attachment; filename="{job_id}.zip"'}
    return Response(
        db.stream_task_content(job_id), mimetype="application/zip", headers=headers
    )


@pipeline_bp.route("/current")
def current_job():
    cj = job_queue.current_job
    if not cj:
        return jsonify({"message": "No job is currently running."})
    return jsonify(
        {
            "id": cj.id,
            "repo_id": cj.repo_id,
            "git_uri": cj.git_uri,
            "status": cj.status,
        }
    )
