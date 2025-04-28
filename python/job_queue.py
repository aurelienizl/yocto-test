# job_queue.py
import os
import subprocess
import threading
import time
import uuid
import datetime
import signal
import shutil
import logging
from logging.handlers import RotatingFileHandler

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class Job:
    STATUS_QUEUED   = "queued"
    STATUS_RUNNING  = "running"
    STATUS_FINISHED = "finished"
    STATUS_FAILED   = "failed"
    STATUS_CANCELED = "canceled"

    def __init__(self, git_uri):
        self.id         = str(uuid.uuid4())
        self.git_uri    = git_uri
        self.status     = Job.STATUS_QUEUED
        self.created_at = datetime.datetime.utcnow().isoformat()
        self.started_at = None
        self.finished_at= None
        self.process    = None
        self._stop_event= threading.Event()

        # Log file & logger
        self.log_file = os.path.join(LOGS_DIR, f"job-{self.id}.log")
        self.logger = logging.getLogger(f"job-{self.id}")
        self.logger.setLevel(logging.INFO)
        fh = RotatingFileHandler(self.log_file,
                                 maxBytes=10*1024*1024,
                                 backupCount=3)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.logger.addHandler(fh)

        # 1-hour timeout (seconds)
        self.timeout = 3600

        # Unique clone directory per job to avoid collisions
        repo = os.path.basename(git_uri.rstrip("/"))
        if repo.endswith(".git"):
            repo = repo[:-4]
        self.clone_dir = os.path.join(TEMP_DIR, f"{repo}-{self.id}")

    def _log(self, level, msg):
        self.logger.log(level, msg)

    def run_command(self, cmd, cwd=None, env=None):
        self._log(logging.INFO, f"⮞ {' '.join(cmd)}")
        start = time.time()

        # start in new process group for full cleanup
        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                cwd=cwd,
                                env=env,
                                universal_newlines=True,
                                preexec_fn=os.setsid)
        self.process = proc

        try:
            while True:
                if self._stop_event.is_set():
                    self._log(logging.WARNING, "Kill requested → terminating group")
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    break

                if time.time() - start > self.timeout:
                    self._log(logging.ERROR, "Timeout exceeded (1 hour) → terminating group")
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    raise subprocess.TimeoutExpired(cmd, self.timeout)

                line = proc.stdout.readline()
                if line:
                    self._log(logging.INFO, line.strip())
                elif proc.poll() is not None:
                    break
                else:
                    time.sleep(0.1)

            proc.wait()
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(proc.returncode, cmd)

        except Exception as e:
            self._log(logging.ERROR, f"Command failed: {e}")
            raise
        finally:
            self.process = None

    def run(self):
        self._log(logging.INFO, f"Starting job for {self.git_uri}")
        self.status     = Job.STATUS_RUNNING
        self.started_at = datetime.datetime.utcnow().isoformat()
        env = os.environ.copy()
        env['HOME'] = BASE_DIR

        try:
            # Ensure a clean clone dir
            shutil.rmtree(self.clone_dir, ignore_errors=True)
            self.run_command(["git", "clone", self.git_uri, self.clone_dir], env=env)

            script = os.path.join(self.clone_dir, ".config", "mirror.sh")
            if os.path.isfile(script):
                self.run_command(["bash", script], cwd=self.clone_dir, env=env)
            else:
                self._log(logging.INFO, "No mirror.sh found, skipping")

            self.status = Job.STATUS_FINISHED
            return True

        except subprocess.TimeoutExpired:
            self._log(logging.ERROR, "Job timed out")
            self.status = Job.STATUS_FAILED
            return False

        except subprocess.CalledProcessError as e:
            if self._stop_event.is_set():
                self._log(logging.WARNING, "Canceled by user")
                self.status = Job.STATUS_CANCELED
            else:
                self._log(logging.ERROR, f"Job error: {e}")
                self.status = Job.STATUS_FAILED
            return False

        finally:
            # always cleanup
            shutil.rmtree(self.clone_dir, ignore_errors=True)
            self.finished_at = datetime.datetime.utcnow().isoformat()

    def kill(self):
        self._stop_event.set()
        if self.process:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            self._log(logging.WARNING, "Process group killed")
        self.status      = Job.STATUS_CANCELED
        self.finished_at= datetime.datetime.utcnow().isoformat()

    def to_dict(self):
        return {
            "id": self.id,
            "git_uri": self.git_uri,
            "status": self.status,
            "log_file": self.log_file,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at
        }


class JobQueue:
    def __init__(self):
        self.queue       = []
        self.jobs        = {}
        self.current_job = None
        self.lock        = threading.Lock()
        self.condition   = threading.Condition(self.lock)

        worker = threading.Thread(target=self.worker, daemon=True)
        worker.start()

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
            self.queue = [j for j in self.queue if j.id != job_id]
            return True, f"Job {job_id} removed from queue."

    def kill_current_job(self):
        with self.lock:
            if self.current_job and self.current_job.status == Job.STATUS_RUNNING:
                self.current_job.kill()
                return True, f"Killed job {self.current_job.id}."
            return False, "No running job to kill."

    def get_jobs(self):
        with self.lock:
            return [j.to_dict() for j in self.jobs.values()]

    def get_job(self, job_id):
        with self.lock:
            return self.jobs.get(job_id)

    def worker(self):
        while True:
            with self.condition:
                while not self.queue:
                    self.condition.wait()
                job = self.queue.pop(0)
                self.current_job = job

            if job.status == Job.STATUS_CANCELED:
                continue

            job.run()

            with self.lock:
                self.current_job = None

    def shutdown(self):
        self.kill_current_job()


# Global instance
job_queue = JobQueue()
