# app.py
import os
import datetime
import signal
import sys
from flask import Flask, request, render_template, jsonify, Response, send_file
from job_queue import job_queue, Job

app = Flask(__name__, template_folder="templates", static_folder="static")

def _shutdown_handler(signum, frame):
    print(f"[{datetime.datetime.utcnow().isoformat()}] Shutdown signal {signum} received, killing job...")
    job_queue.shutdown()
    sys.exit(0)

signal.signal(signal.SIGINT,  _shutdown_handler)
signal.signal(signal.SIGTERM, _shutdown_handler)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/enqueue", methods=["POST"])
def enqueue():
    git_uri = request.form.get("git_uri", "").strip()
    if not git_uri:
        return jsonify({"error": "No Git URI provided"}), 400
    job = Job(git_uri)
    job_queue.add_job(job)
    return jsonify({"message": "Job enqueued", "job": job.to_dict()})


@app.route("/tasks", methods=["GET"])
def list_tasks():
    return jsonify(job_queue.get_jobs())


@app.route("/kill", methods=["POST"])
def kill_job():
    success, msg = job_queue.kill_current_job()
    status = 200 if success else 400
    return jsonify({"message": msg} if success else {"error": msg}), status


@app.route("/remove", methods=["POST"])
def remove_job():
    job_id = request.form.get("job_id", "").strip()
    if not job_id:
        return jsonify({"error": "No job ID provided"}), 400
    success, msg = job_queue.remove_job(job_id)
    status = 200 if success else 400
    return jsonify({"message": msg} if success else {"error": msg}), status


@app.route("/logs/<job_id>")
def get_logs(job_id):
    job = job_queue.get_job(job_id)
    if not job:
        return "Job not found.", 404
    if not os.path.exists(job.log_file):
        return "No log available yet.", 404
    return send_file(job.log_file)


@app.route("/stream_logs/<job_id>")
def stream_logs(job_id):
    job = job_queue.get_job(job_id)
    if not job:
        return "Job not found.", 404

    def generate():
        with open(job.log_file, "r") as f:
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line}\n\n"
                else:
                    time.sleep(1)

    return Response(generate(),
                    mimetype="text/event-stream",
                    headers={"Cache-Control":"no-cache",
                             "Connection":"keep-alive"})


@app.route("/current")
def current_job():
    cj = job_queue.current_job
    if cj:
        return jsonify(cj.to_dict())
    return jsonify({"message": "No job is currently running."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
