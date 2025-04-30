# job_queue.py
import threading
import datetime
from db import db
from job import Job


class JobQueue:
    def __init__(self):
        self.queue = []
        self.jobs = {}
        self.current_job = None
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.worker_thread = threading.Thread(target=self.worker, daemon=True)
        self.worker_thread.start()

    def add_job(self, job: Job):
        with self.condition:
            self.jobs[job.id] = job
            self.queue.append(job)
            self.condition.notify()
        return job

    def remove_job(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return False, "Job not found."
            if job.status != Job.STATUS_QUEUED:
                return False, "Only queued jobs can be removed."
            job.status = Job.STATUS_CANCELED
            job.finished_at = datetime.datetime.utcnow().isoformat()
            db.update_task_status(job.id, job.status, finished_at=job.finished_at)
            self.queue = [j for j in self.queue if j.id != job_id]
            return True, f"Job {job_id} removed from queue."

    def kill_current_job(self):
        with self.lock:
            if self.current_job and self.current_job.status == Job.STATUS_RUNNING:
                self.current_job.kill()
                return True, f"Killed job {self.current_job.id}."
            return False, "No running job to kill."

    def worker(self):
        while True:
            with self.condition:
                while not self.queue:
                    self.condition.wait()
                job = self.queue.pop(0)

            if job is None:
                break

            with self.lock:
                self.current_job = job

            if job.status == Job.STATUS_CANCELED:
                with self.lock:
                    self.current_job = None
                continue

            job.run()

            with self.lock:
                self.current_job = None

    def shutdown(self):
        with self.lock:
            for job in self.queue:
                if job is not None:
                    job.status = Job.STATUS_CANCELED
                    ts = datetime.datetime.utcnow().isoformat()
                    db.update_task_status(job.id, job.status, finished_at=ts)
            self.queue.clear()
            self.queue.append(None)

        with self.condition:
            self.condition.notify_all()
        self.worker_thread.join()


# Global instance
job_queue = JobQueue()
