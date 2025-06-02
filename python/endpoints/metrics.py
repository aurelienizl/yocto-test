from __future__ import annotations

import psutil
import shutil
from flask import Blueprint, jsonify

metrics_bp = Blueprint("metrics", __name__)


@metrics_bp.route("/metrics/cpu")
def metrics_cpu():
    return jsonify({"cpu_percent": psutil.cpu_percent(interval=1)})


@metrics_bp.route("/metrics/memory")
def metrics_memory():
    m = psutil.virtual_memory()
    return jsonify({"total": m.total, "available": m.available, "percent": m.percent})


@metrics_bp.route("/metrics/disk")
def metrics_disk():
    du = shutil.disk_usage("/")
    percent = round(du.used / du.total * 100, 1)
    return jsonify({"total": du.total, "used": du.used, "free": du.free, "percent": percent})