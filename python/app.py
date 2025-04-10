import os
import time
import datetime
from flask import Flask, request, render_template, jsonify, Response, send_file
from job_queue import job_queue, Job  # Import the global job_queue and Job

app = Flask(__name__, template_folder="templates", static_folder="static")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/enqueue", methods=["POST"])
def enqueue():
    """Enqueue a new Git repository job."""
    git_uri = request.form.get("git_uri", "").strip()
    if not git_uri:
        return jsonify({"error": "No Git URI provided"}), 400
    job = Job(git_uri)
    job_queue.add_job(job)
    return jsonify({"message": "Job enqueued successfully", "job": job.to_dict()})

@app.route("/tasks", methods=["GET"])
def get_jobs():
    """Return a JSON list of all jobs."""
    return jsonify(job_queue.get_jobs())

@app.route("/kill", methods=["POST"])
def kill_job():
    """Kill the currently running job."""
    success, message = job_queue.kill_current_job()
    if not success:
        return jsonify({"error": message}), 400
    return jsonify({"message": message})

@app.route("/remove", methods=["POST"])
def remove_job():
    """Remove a queued job from the queue."""
    job_id = request.form.get("job_id", "").strip()
    if not job_id:
        return jsonify({"error": "No job ID provided"}), 400
    success, message = job_queue.remove_job(job_id)
    if not success:
        return jsonify({"error": message}), 400
    return jsonify({"message": message})

@app.route("/logs/<job_id>")
def get_logs(job_id):
    """Return the log file for a given job."""
    job = job_queue.jobs.get(job_id)
    if not job:
        return "Job not found.", 404
    if not os.path.exists(job.log_file):
        return "No log available yet.", 404
    return send_file(job.log_file)

@app.route("/stream_logs/<job_id>")
def stream_logs(job_id):
    """Stream a job's log file."""
    job = job_queue.jobs.get(job_id)
    if not job:
        return "Job not found.", 404

    def generate():
        with open(job.log_file, "r") as f:
            # Uncomment the next line if you wish to start at the end of file:
            # f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line}\n\n"
                else:
                    time.sleep(1)
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

@app.route("/current")
def current_job():
    """Return the currently running job, if any."""
    current = job_queue.get_current_job()
    if current:
        return jsonify(current)
    else:
        return jsonify({"message": "No job is currently running."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
