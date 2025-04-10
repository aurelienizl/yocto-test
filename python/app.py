import os
import time
import datetime
from flask import Flask, request, render_template, jsonify, Response, send_file
from mirror import (
    Task,
    tasks_lock,
    tasks_queue,
    tasks,
    new_task_cond,
    currently_running_task,
)

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/enqueue", methods=["POST"])
def enqueue():
    """Enqueue a new Git repository task."""
    git_uri = request.form.get("git_uri", "").strip()
    if not git_uri:
        return jsonify({"error": "No Git URI provided"}), 400
    task = Task(git_uri)
    with tasks_lock:
        tasks[task.id] = task
        tasks_queue.append(task)
        new_task_cond.notify()
    return jsonify({"message": "Task enqueued successfully", "task": task.to_dict()})


@app.route("/tasks", methods=["GET"])
def get_tasks():
    """Return JSON list of all tasks."""
    with tasks_lock:
        all_tasks = [task.to_dict() for task in tasks.values()]
    return jsonify(all_tasks)


@app.route("/kill", methods=["POST"])
def kill_task():
    """Kill the currently running task."""
    global currently_running_task
    with tasks_lock:
        if currently_running_task and currently_running_task.runner:
            currently_running_task.runner.kill()
            currently_running_task.status = "canceled"
            currently_running_task.finished_at = datetime.datetime.utcnow().isoformat()
            message = f"Task {currently_running_task.id} killed."
        else:
            return jsonify({"error": "No running task to kill."}), 400
    return jsonify({"message": message})


@app.route("/remove", methods=["POST"])
def remove_task():
    """Remove a queued task from the queue."""
    task_id = request.form.get("task_id", "").strip()
    if not task_id:
        return jsonify({"error": "No task ID provided"}), 400
    with tasks_lock:
        task = tasks.get(task_id)
        if not task:
            return jsonify({"error": "Task not found."}), 404
        if task.status != "queued":
            return jsonify({"error": "Only queued tasks can be removed."}), 400
        task.status = "canceled"
        task.finished_at = datetime.datetime.utcnow().isoformat()
        tasks_queue[:] = [t for t in tasks_queue if t.id != task_id]
    return jsonify({"message": f"Task {task_id} removed from queue."})


@app.route("/logs/<task_id>")
def get_logs(task_id):
    """Return log file for a given task."""
    task = tasks.get(task_id)
    if not task:
        return "Task not found.", 404
    if not os.path.exists(task.log_file):
        return "No log available yet.", 404
    return send_file(task.log_file)


@app.route("/stream_logs/<task_id>")
def stream_logs(task_id):
    task = tasks.get(task_id)
    if not task:
        return "Task not found.", 404

    def generate():
        with open(task.log_file, "r") as f:
            # Do not seek to the end if you want all logs to be streamed.
            # Remove or comment out the next line:
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
def current_task():
    """Return the currently running task, if any."""
    with tasks_lock:
        if currently_running_task:
            return jsonify(currently_running_task.to_dict())
        else:
            return jsonify({"message": "No task is currently running."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
