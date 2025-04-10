import os
import subprocess
import threading
import time
import uuid
import datetime

# Base setup for directories.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class Job:
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_FINISHED = "finished"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"

    def __init__(self, git_uri):
        self.id = str(uuid.uuid4())
        self.git_uri = git_uri
        self.status = Job.STATUS_QUEUED
        self.log_file = os.path.join(LOGS_DIR, f"job-{self.id}.log")
        self.created_at = datetime.datetime.utcnow().isoformat()
        self.started_at = None
        self.finished_at = None
        self.process = None
        self._stop_event = threading.Event()
        # Derive repository name.
        repo_name = os.path.basename(git_uri.rstrip("/"))
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        self.clone_dir = os.path.join(TEMP_DIR, repo_name)

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

    def _log(self, message):
        """Append a timestamped message to the job log and print it."""
        timestamp = datetime.datetime.utcnow().isoformat()
        log_message = f"[{timestamp}] {message}"
        with open(self.log_file, "a") as f:
            f.write(log_message + "\n")
            f.flush()
        print(log_message)

    def run_command(self, command, cwd=None, env=None):
        """Run a command with streaming output and support cancellation."""
        self._log(f"Running command: {' '.join(command)}")
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=cwd,
                env=env,
                universal_newlines=True
            )
            # Stream the command output.
            while True:
                if self._stop_event.is_set():
                    self._log("Kill signal received. Terminating process.")
                    self.process.kill()
                    break
                line = self.process.stdout.readline()
                if line:
                    self._log(line.strip())
                elif self.process.poll() is not None:
                    break
                else:
                    time.sleep(0.1)
            self.process.wait()
            ret = self.process.returncode
            self.process = None
            if ret != 0:
                raise subprocess.CalledProcessError(ret, command)
        except Exception as e:
            self._log(f"Command {' '.join(command)} failed: {e}")
            raise

    def run(self):
        """Execute the job: clone repository, run mirror script (if exists),
        and clean up the clone directory."""
        self._log(f"Starting job for repository: {self.git_uri}")
        self.status = Job.STATUS_RUNNING
        self.started_at = datetime.datetime.utcnow().isoformat()
        env = os.environ.copy()
        env['HOME'] = BASE_DIR
        try:
            # Check if the clone directory already exists.
            if os.path.exists(self.clone_dir):
                self._log(f"Clone directory {self.clone_dir} already exists. Removing it.")
                self.run_command(["rm", "-rf", self.clone_dir])

            # Clone the repository.
            self._log(f"Cloning {self.git_uri} into {self.clone_dir}")
            self.run_command(["git", "clone", self.git_uri, self.clone_dir], env=env)

            # Execute mirror.sh if present.
            script_path = os.path.join(self.clone_dir, ".config", "mirror.sh")
            if os.path.isfile(script_path):
                self._log(f"Executing mirror script: {script_path}")
                self.run_command(["bash", script_path], cwd=self.clone_dir, env=env)
            else:
                self._log(f"No mirror script found at {script_path}")

            # Clean up the clone directory.
            self._log(f"Cleaning up clone at {self.clone_dir}")
            self.run_command(["rm", "-rf", self.clone_dir])
            self.status = Job.STATUS_FINISHED
            return True

        except subprocess.CalledProcessError as e:
            # Check if the stop event was set, meaning the job was intentionally cancelled.
            if self._stop_event.is_set():
                self._log("Job was canceled; not marking as failed.")
                self.status = Job.STATUS_CANCELED
            else:
                self._log(f"Job failed with error: {e}")
                self.status = Job.STATUS_FAILED
            return False

        finally:
            self.finished_at = datetime.datetime.utcnow().isoformat()


    def kill(self):
        """Attempt to kill the current running process."""
        self._stop_event.set()
        if self.process:
            self.process.kill()
            self._log("Process killed.")
        self.status = Job.STATUS_CANCELED
        self.finished_at = datetime.datetime.utcnow().isoformat()


class JobQueue:
    def __init__(self):
        self.queue = []  # List of pending jobs.
        self.jobs = {}   # Dictionary to store all jobs (by job ID).
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.current_job = None
        # Launch the background worker thread.
        self.worker_thread = threading.Thread(target=self.worker, daemon=True)
        self.worker_thread.start()

    def add_job(self, job: Job):
        """Add a job to the queue and notify the worker."""
        with self.condition:
            self.jobs[job.id] = job
            self.queue.append(job)
            self.condition.notify()
        return job

    def remove_job(self, job_id):
        """Remove a queued job by its ID (only if still waiting)."""
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
        """Kill the currently running job, if any."""
        with self.lock:
            if self.current_job and self.current_job.status == Job.STATUS_RUNNING:
                self.current_job.kill()
                return True, f"Job {self.current_job.id} killed."
            else:
                return False, "No running job to kill."

    def worker(self):
        """Background worker that processes jobs sequentially."""
        while True:
            with self.condition:
                while not self.queue:
                    self.condition.wait()
                job = self.queue.pop(0)
                self.current_job = job
            if job.status == Job.STATUS_CANCELED:
                continue
            print(f"Starting job {job.id} at {datetime.datetime.utcnow().isoformat()}")
            job.run()
            print(f"Finished job {job.id} with status {job.status} at {job.finished_at}")
            with self.lock:
                self.current_job = None

    def get_jobs(self):
        with self.lock:
            return [job.to_dict() for job in self.jobs.values()]

    def get_current_job(self):
        with self.lock:
            return self.current_job.to_dict() if self.current_job else None

# Create a global JobQueue instance.
job_queue = JobQueue()
