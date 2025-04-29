# job.py
from db import db
import os
import subprocess
import threading
import time
import uuid
import datetime
import signal
import logging
import shutil
import tempfile

class Job:
    STATUS_QUEUED   = 'queued'
    STATUS_RUNNING  = 'running'
    STATUS_FINISHED = 'finished'
    STATUS_FAILED   = 'failed'
    STATUS_CANCELED = 'canceled'

    def __init__(self, git_uri):
        self.id         = str(uuid.uuid4())
        self.git_uri    = git_uri
        self.status     = Job.STATUS_QUEUED
        self.created_at = datetime.datetime.utcnow().isoformat()
        self.started_at = None
        self.finished_at= None
        self.process    = None
        self._stop_event= threading.Event()

        db.create_task(self.id, self.git_uri, self.created_at)

        self._temp_dir_obj = tempfile.TemporaryDirectory(prefix=f'repo-{self.id}-')
        self.clone_dir = self._temp_dir_obj.name
        self.timeout = 3600

    def _log(self, level, msg):
        ts = datetime.datetime.utcnow().isoformat()
        db.add_log(self.id, ts, msg)

    def run_command(self, cmd, cwd=None, env=None):
        self._log(logging.INFO, f"{' '.join(cmd)}")
        start = time.time()
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=cwd, env=env, universal_newlines=True,
            preexec_fn=os.setsid
        )
        self.process = proc

        try:
            while True:
                if self._stop_event.is_set():
                    self._log(logging.WARNING, 'Kill requested → terminating group')
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    break
                if time.time() - start > self.timeout:
                    self._log(logging.ERROR, 'Timeout exceeded → terminating')
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    raise subprocess.TimeoutExpired(cmd, self.timeout)

                line = proc.stdout.readline()
                if line:
                    self._log(logging.INFO, line.strip())
                elif proc.poll() is not None:
                    break
                else:
                    time.sleep(1)

            proc.wait()
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(proc.returncode, cmd)
        except Exception as e:
            self._log(logging.ERROR, f'Command failed: {e}')
            raise
        finally:
            self.process = None

    def run(self):
        self.status = Job.STATUS_RUNNING
        self.started_at = datetime.datetime.utcnow().isoformat()
        db.update_task_status(self.id, self.status, started_at=self.started_at)

        env = os.environ.copy()
        env['HOME'] = os.path.abspath(os.path.dirname(__file__))

        try:
            shutil.rmtree(self.clone_dir, ignore_errors=True)
            self.run_command(['git', 'clone', self.git_uri, self.clone_dir], env=env)

            script = os.path.join(self.clone_dir, '.config', 'mirror.sh')
            if os.path.isfile(script):
                self.run_command(['bash', script], cwd=self.clone_dir, env=env)
            else:
                self._log(logging.INFO, 'No mirror.sh found, skipping')

            self.status = Job.STATUS_FINISHED
            self.finished_at = datetime.datetime.utcnow().isoformat()
            db.update_task_status(
                self.id, self.status,
                finished_at=self.finished_at
            )
            return True

        except subprocess.TimeoutExpired:
            self.status = Job.STATUS_FAILED
            self.finished_at = datetime.datetime.utcnow().isoformat()
            db.update_task_status(self.id, self.status, finished_at=self.finished_at)
            return False

        except subprocess.CalledProcessError:
            if self._stop_event.is_set():
                self.status = Job.STATUS_CANCELED
            else:
                self.status = Job.STATUS_FAILED
            self.finished_at = datetime.datetime.utcnow().isoformat()
            db.update_task_status(self.id, self.status, finished_at=self.finished_at)
            return False

        finally:
            self._temp_dir_obj.cleanup()

    def kill(self):
        self._stop_event.set()
        if self.process:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            self._log(logging.WARNING, 'Process group killed')
        self.status = Job.STATUS_CANCELED
        self.finished_at = datetime.datetime.utcnow().isoformat()
        db.update_task_status(self.id, self.status, finished_at=self.finished_at)
        self._temp_dir_obj.cleanup()
