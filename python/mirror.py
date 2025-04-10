import os
import subprocess
import threading
import time
import uuid
import datetime

# Set base directories.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class Task:
    """Represents a repository processing task."""
    def __init__(self, git_uri):
        self.id = str(uuid.uuid4())
        self.git_uri = git_uri
        self.status = "queued"  # queued, running, finished, failed, canceled.
        self.log_file = os.path.join(LOGS_DIR, f"task-{self.id}.log")
        self.created_at = datetime.datetime.utcnow().isoformat()
        self.started_at = None
        self.finished_at = None
        self.runner = None

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

class GitMirrorRunner:
    """
    Clones a repository, runs a mirror.sh script (if present), and cleans up.
    Uses subprocess.Popen so that output is streamed and tasks can be killed.
    """
    def __init__(self, git_uri, temp_dir=TEMP_DIR, log_file=None):
        self.git_uri = git_uri
        self.temp_dir = temp_dir
        self.log_file = log_file or os.path.join(LOGS_DIR, "build_mirror.log")
        self.repo_name = os.path.basename(git_uri)
        if self.repo_name.endswith('.git'):
            self.repo_name = self.repo_name[:-4]
        self.clone_dir = os.path.join(self.temp_dir, self.repo_name)
        self.process = None
        self._stop_event = threading.Event()

    def _log(self, message):
        timestamp = datetime.datetime.utcnow().isoformat()
        log_message = f"[{timestamp}] {message}"
        with open(self.log_file, 'a') as f:
            f.write(log_message + "\n")
        print(log_message)

    def run_command(self, command, cwd=None, env=None):
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
            # Stream output and check periodically for kill signal.
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
        os.makedirs(self.temp_dir, exist_ok=True)
        env = os.environ.copy()
        env['HOME'] = BASE_DIR
        try:
            self._log(f"Cloning {self.git_uri} into {self.clone_dir}")
            self.run_command(["git", "clone", self.git_uri, self.clone_dir], env=env)

            # Execute mirror.sh if present.
            script_path = os.path.join(self.clone_dir, ".config", "mirror.sh")
            if os.path.isfile(script_path):
                self._log(f"Executing mirror script: {script_path}")
                self.run_command(["bash", script_path], cwd=self.clone_dir, env=env)
            else:
                self._log(f"No mirror script found at {script_path}")

            self._log(f"Cleaning up clone at {self.clone_dir}")
            self.run_command(["rm", "-rf", self.clone_dir])
            return True
        except subprocess.CalledProcessError as e:
            self._log(f"Error during processing: {e}")
            return False

    def kill(self):
        self._stop_event.set()
        if self.process:
            self.process.kill()
            self._log("Process killed.")

# Global task variables.
tasks_lock = threading.Lock()
tasks_queue = []   # List of pending tasks.
tasks = {}         # Dictionary of all tasks, keyed by task id.
currently_running_task = None
new_task_cond = threading.Condition(lock=tasks_lock)

def task_worker():
    """Background worker loop to process tasks sequentially."""
    global currently_running_task
    while True:
        with new_task_cond:
            while not tasks_queue:
                new_task_cond.wait()
            task = tasks_queue.pop(0)
        if task.status == "canceled":
            continue
        with tasks_lock:
            currently_running_task = task
            task.status = "running"
            task.started_at = datetime.datetime.utcnow().isoformat()
        runner = GitMirrorRunner(task.git_uri, log_file=task.log_file)
        task.runner = runner
        success = runner.run()
        with tasks_lock:
            if success:
                task.status = "finished"
            else:
                task.status = "failed"
            task.finished_at = datetime.datetime.utcnow().isoformat()
            currently_running_task = None

# Start the background task worker thread.
worker_thread = threading.Thread(target=task_worker, daemon=True)
worker_thread.start()
