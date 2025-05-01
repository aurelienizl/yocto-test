import datetime
import signal
import sys
from flask import Flask, render_template
from job_queue import job_queue
from db import db
from endpoints.pipeline import pipeline_bp
from endpoints.metrics import metrics_bp

app = Flask(__name__, template_folder="templates", static_folder="static")

# Register Blueprints
app.register_blueprint(pipeline_bp)
app.register_blueprint(metrics_bp)

# Root-level routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/repos")
def repos():
    return render_template("repos.html")

# Graceful shutdown handler
def _shutdown_handler(signum, frame):
    print(
        f"[{datetime.datetime.utcnow().isoformat()}] Shutdown signal {signum}",
        file=sys.stderr,
    )
    job_queue.shutdown()
    sys.exit(0)

signal.signal(signal.SIGINT, _shutdown_handler)
signal.signal(signal.SIGTERM, _shutdown_handler)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
