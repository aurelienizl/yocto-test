"""Flask entry-point wired for the BuildOS refactor."""
from __future__ import annotations

import datetime
import signal
import sys

from flask import Flask, render_template

from buildos_job.queue import job_queue
from buildos_db import db  # noqa – used by blueprints

from endpoints.pipeline import pipeline_bp
from endpoints.metrics import metrics_bp

__all__ = ["create_app"]


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # blueprints
    app.register_blueprint(pipeline_bp)
    app.register_blueprint(metrics_bp)

    # views
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/repos")
    def repos():
        return render_template("repos.html")

    # graceful shutdown
    def _shutdown_handler(signum, _frame):
        print(
            f"[{datetime.datetime.utcnow().isoformat()}] Shutdown signal {signum}",
            file=sys.stderr,
        )
        job_queue.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    return app

# development run (gunicorn / waitress etc. in prod)
if __name__ == "__main__":
    _app = create_app()
    _app.run(host="0.0.0.0", port=5000, threaded=True)