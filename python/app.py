"""Flask entry-point for BuildOS (UI + API)"""
from __future__ import annotations

import datetime
import signal
import sys

from flask import Flask, render_template

# ── BuildOS blueprints ────────────────────────────────────────────
from endpoints.pipeline import pipeline_bp         # REST: /pipeline/…
from endpoints.metrics  import metrics_bp          # REST: /metrics/…
from endpoints.mirror   import mirror_bp           # REST: /mirror/…

from buildos_job.queue import job_queue
from buildos_db import db                          # noqa: used by blueprints

__all__ = ["create_app"]


# ──────────────────────────────────────────────────────────────────
#  Factory
# ──────────────────────────────────────────────────────────────────
def create_app() -> Flask:
    """
    Assemble the Flask application with
      • REST endpoints under /pipeline, /metrics, /mirror
      • Static single-page UIs at  /, /pipeline, /mirror
    """
    app = Flask(
        __name__,
        template_folder="templates",     # index.html, pipeline.html, mirror.html …
        static_folder="static",          # apps.js, *.css, *.js, icons …
    )

    # ――― REST blueprints ―――
    # Prefix the API routes so they don’t clash with the UI root paths.
    app.register_blueprint(pipeline_bp, url_prefix="/pipeline")
    app.register_blueprint(metrics_bp)
    app.register_blueprint(mirror_bp,  url_prefix="/mirror")

    # ――― UI routes ―――
    # Each route simply ships the matching HTML page; the page’s JS pulls
    # its own assets from /static and calls the REST endpoints above.
    @app.route("/")
    def index() -> str:            # Landing page: app grid
        return render_template("index.html")

    @app.route("/pipeline")
    def pipeline_ui() -> str:      # CI/CD dashboard
        return render_template("pipeline.html")

    @app.route("/mirror")
    def mirror_ui() -> str:        # Web file-manager
        return render_template("mirror.html")

    # ――― Graceful shutdown ―――
    def _shutdown(signum: int, _frame) -> None:
        print(f"[{datetime.datetime.utcnow().isoformat()}] Shutdown signal {signum}", file=sys.stderr)
        job_queue.shutdown()       # stop any running worker cleanly
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    return app


# ── Dev entry-point (use gunicorn / uvicorn / waitress in production) ──
if __name__ == "__main__":
    app = create_app()
    # threaded=True lets log polling + uploads run concurrently on dev server
    app.run(host="0.0.0.0", port=5000, threaded=True)
