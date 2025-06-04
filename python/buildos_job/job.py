# -----------------------------------------------------------------------------
# LIBRARY: buildos_job
# FILE: buildos_job/job.py
# AUTHOR: aurelien.izoulet
# LICENSE: Apache License 2.0
# -----------------------------------------------------------------------------

from __future__ import annotations

import datetime as _dt
import logging as _log
import os as _os
import shutil as _shutil
import signal as _signal
import subprocess as _sp
import tempfile as _tmp
import threading as _th
import time as _time
import uuid as _uuid
from pathlib import Path as _Path
from typing import Optional

from buildos_db import db


class JobCancelled(Exception):
    """Raised internally when a job is cancelled by the user."""


class Job:
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_FINISHED = "finished"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"

    def __init__(self, repo_id: str, timeout: int = 3600):
        repo = db.get_repository(repo_id)
        if not repo:
            raise ValueError(f"Repo {repo_id} missing")

        self.repo_id = repo_id
        self.git_uri = repo["git_uri"]
        self.id = str(_uuid.uuid4())

        self.status = Job.STATUS_QUEUED
        self.created_at = _dt.datetime.utcnow().isoformat()
        self.started_at: Optional[str] = None
        self.finished_at: Optional[str] = None

        self.timeout = timeout
        self.process: Optional[_sp.Popen] = None
        self._stop_event = _th.Event()

        db.create_task(self.id, self.repo_id, self.created_at)

        self._tmpdir = _tmp.TemporaryDirectory(prefix=f"repo-{self.id}-")
        self.clone_dir = _Path(self._tmpdir.name)
        self.home_dir = self.clone_dir / "_home"
        self.home_dir.mkdir(exist_ok=True)

    def _log(self, lvl, msg):
        db.add_log(self.id, _dt.datetime.utcnow().isoformat(), str(msg))
        _log.log(lvl, str(msg))

    def _maybe_abort(self):
        if self._stop_event.is_set():
            raise JobCancelled()

    def _terminate_pg(self):
        if self.process and self.process.poll() is None:
            if _os.name == "posix":
                _os.killpg(_os.getpgid(self.process.pid), _signal.SIGTERM)
            else:
                self.process.terminate()
            self._log(_log.WARNING, "Process group terminated")

    def _run(self, cmd: list[str], *, cwd: Optional[_Path] = None, env=None):
        self._log(_log.INFO, " ".join(cmd))
        start = _time.time()
        env = env or _os.environ.copy()
        self.process = _sp.Popen(
            cmd,
            stdout=_sp.PIPE,
            stderr=_sp.STDOUT,
            cwd=str(cwd) if cwd else None,
            env=env,
            universal_newlines=True,
            preexec_fn=(_os.setsid if _os.name == "posix" else None),
        )
        try:
            while True:
                if self._stop_event.is_set():
                    self._terminate_pg()
                    raise JobCancelled()
                if _time.time() - start > self.timeout:
                    self._log(_log.ERROR, "Timeout exceeded")
                    self._terminate_pg()
                    raise _sp.TimeoutExpired(cmd, self.timeout)
                line = self.process.stdout.readline()
                if line:
                    self._log(_log.INFO, line.rstrip())
                elif self.process.poll() is not None:
                    break
                else:
                    _time.sleep(5)
            if self.process.returncode != 0:
                raise _sp.CalledProcessError(self.process.returncode, cmd)
        finally:
            self.process = None

    # ---------------- main workflow ----------------
    def run(self) -> bool:
        self.status = Job.STATUS_RUNNING
        self.started_at = _dt.datetime.utcnow().isoformat()
        db.update_task_status(self.id, self.status, started_at=self.started_at)

        env = _os.environ.copy()
        env["HOME"] = str(self.home_dir)
        try:
            _shutil.rmtree(self.clone_dir, ignore_errors=True)
            self._run(["git", "clone", self.git_uri, str(self.clone_dir)], env=env)
            self._maybe_abort()

            script = self.clone_dir / ".config" / "pipeline.sh"
            if script.is_file():
                self._run(["bash", str(script)], cwd=self.clone_dir, env=env)
                self._maybe_abort()
            else:
                self._log(_log.INFO, "No pipeline.sh found – skipping")

            result_dir = self.clone_dir / ".result"
            if result_dir.is_dir():
                self._maybe_abort()
                try:
                    zip_path = _shutil.make_archive(
                        str(self.clone_dir / self.id), "zip", str(result_dir)
                    )
                    with open(zip_path, "rb") as fh:
                        db.update_task_content(self.id, fh.read())
                    self._log(_log.INFO, f"Archived results -> {zip_path}")
                except Exception as exc:
                    self._log(_log.ERROR, f"Archive failed: {exc}")
                    raise
            else:
                self._log(_log.INFO, "No .result directory – nothing to archive")

            self.status = Job.STATUS_FINISHED
            return True

        except JobCancelled:
            self.status = Job.STATUS_CANCELED
        except (_sp.TimeoutExpired, _sp.CalledProcessError, Exception):
            if self.status != Job.STATUS_CANCELED:
                self.status = Job.STATUS_FAILED
        finally:
            self.finished_at = _dt.datetime.utcnow().isoformat()
            db.update_task_status(self.id, self.status, finished_at=self.finished_at)
            try:
                self._tmpdir.cleanup()
            except FileNotFoundError:
                pass
        return False

    def kill(self):
        self._stop_event.set()
        self._terminate_pg()
