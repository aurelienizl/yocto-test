# -----------------------------------------------------------------------------
# LIBRARY: buildos_job
# FILE: buildos_job/queue.py
# AUTHOR: aurelien.izoulet
# LICENSE: Apache License 2.0
# -----------------------------------------------------------------------------
from __future__ import annotations

import datetime
import threading
from typing import Dict, List, Optional
import datetime as _dt


from buildos_db import db
from .job import Job


class JobQueue:
    def __init__(self):
        self._queue: List[Job] = []
        self._jobs: Dict[str, Job] = {}
        self.current_job: Optional[Job] = None

        import threading

        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._worker = threading.Thread(target=self._loop, daemon=True)
        self._worker.start()

    # ------------ public ------------
    def enqueue(self, repo_id: str, *, timeout: int = 3600) -> Job:
        job = Job(repo_id, timeout)
        with self._cond:
            self._jobs[job.id] = job
            self._queue.append(job)
            self._cond.notify()
        return job

    def remove_job(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != Job.STATUS_QUEUED:
                return False, "Job not removable"
            job.status = Job.STATUS_CANCELED
            ts = _dt.datetime.utcnow().isoformat()
            db.update_task_status(job.id, job.status, finished_at=ts)
            self._queue = [j for j in self._queue if j.id != job_id]
            return True, f"Job {job_id} cancelled"

    def kill_current_job(self):
        with self._lock:
            if self.current_job and self.current_job.status == Job.STATUS_RUNNING:
                self.current_job.kill()
                return True, f"Killed {self.current_job.id}"
            return False, "Nothing running"

    def shutdown(self):
        with self._lock:
            for j in self._queue:
                j.status = Job.STATUS_CANCELED
                ts = _dt.datetime.utcnow().isoformat()
                db.update_task_status(j.id, j.status, finished_at=ts)
            self._queue.clear()
            self._queue.append(None)

        with self._cond:
            self._cond.notify_all()

        self._worker.join()

    # ------------ worker ------------
    def _loop(self):
        while True:
            with self._cond:
                while not self._queue:
                    self._cond.wait()
                job = self._queue.pop(0)
            if job is None:
                break
            with self._lock:
                self.current_job = job
            if job.status != Job.STATUS_CANCELED:
                job.run()
            with self._lock:
                self.current_job = None


job_queue = JobQueue()
