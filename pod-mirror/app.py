import os
import subprocess
import threading
from flask import Flask, request, render_template, jsonify, Response

# Paths and constants
LOG_FILE = '/home/generic/build_mirror.log'
TEMP_DIR = '/home/generic/temp'

app = Flask(__name__, template_folder='templates')

# Global variables to control concurrency
operation_lock = threading.Lock()
operation_running = False

class GitMirrorRunner:
    """
    A class that clones a Git repository, executes the mirror script (if present),
    and cleans up the temporary clone. All log messages are written to LOG_FILE.
    """
    def __init__(self, git_uri, temp_dir=TEMP_DIR, log_file=LOG_FILE):
        self.git_uri = git_uri
        self.temp_dir = temp_dir
        self.log_file = log_file

        # Extract repository name from the URI; remove '.git' if present.
        self.repo_name = os.path.basename(git_uri)
        if self.repo_name.endswith('.git'):
            self.repo_name = self.repo_name[:-4]
        self.clone_dir = os.path.join(self.temp_dir, self.repo_name)

    def _log(self, message):
        """
        Append a message to the log file and also print it to the console.
        """
        with open(self.log_file, 'a') as f:
            f.write(message + "\n")
        print(message)

    def run(self):
        """
        Perform the clone, mirror.sh execution (if available), and cleanup.
        """
        # Ensure the temporary directory exists.
        os.makedirs(self.temp_dir, exist_ok=True)

        # Prepare a clean environment for subprocesses.
        env = os.environ.copy()
        env['HOME'] = '/home/generic'

        self._log(f"Cloning {self.git_uri} into {self.clone_dir}")

        try:
            with open(self.log_file, 'a') as log_f:
                subprocess.run(
                    ["git", "clone", self.git_uri, self.clone_dir],
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    check=True
                )
        except subprocess.CalledProcessError as e:
            self._log(f"Error cloning {self.git_uri}: {e}")
            return False

        # Look for .config/mirror.sh in the repository root.
        script_path = os.path.join(self.clone_dir, ".config", "mirror.sh")
        if os.path.isfile(script_path):
            self._log(f"Executing script {script_path}")
            try:
                with open(self.log_file, 'a') as log_f:
                    subprocess.run(
                        ["bash", script_path],
                        cwd=self.clone_dir,  # set working directory to repo's root
                        stdout=log_f,
                        stderr=subprocess.STDOUT,
                        env=env,
                        check=True
                    )
            except subprocess.CalledProcessError as e:
                self._log(f"Error executing script {script_path}: {e}")
        else:
            self._log(f"No mirror script found at {script_path}")

        # Clean up the temporary clone.
        self._log(f"Cleaning up clone at {self.clone_dir}")
        try:
            subprocess.run(["rm", "-rf", self.clone_dir], check=True)
        except subprocess.CalledProcessError as e:
            self._log(f"Error cleaning up {self.clone_dir}: {e}")

        return True

def background_operation(git_uri):
    """
    Runs the GitMirrorRunner and sets the global flag appropriately.
    """
    global operation_running
    runner = GitMirrorRunner(git_uri)
    # Optionally, you may choose to clear or preserve the log file.
    # Here we clear the log file at the beginning of an operation.
    with open(LOG_FILE, 'w') as f:
        f.write("")
    runner.run()
    with operation_lock:
        operation_running = False

# SSE log stream endpoint.
def stream_logs():
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, 'w').close()
    with open(LOG_FILE, 'r') as f:
        # Move to the end so only new logs are streamed.
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                yield f"data: {line.strip()}\n\n"
            else:
                # Pause briefly to avoid busy-waiting.
                import time
                time.sleep(1)

@app.route('/', methods=['GET'])
def index():
    """
    Render the main page with the form and log terminal.
    """
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run_git():
    """
    Accept a Git URI via POST.
    If an operation is already running, return an error.
    Otherwise, start the mirror operation in a background thread.
    """
    global operation_running
    git_uri = request.form.get('git_uri', '').strip()
    if not git_uri:
        return jsonify({"error": "No Git URI provided"}), 400

    with operation_lock:
        if operation_running:
            return jsonify({"error": "An operation is already running."}), 409
        else:
            operation_running = True

    # Start the background operation in a thread.
    thread = threading.Thread(target=background_operation, args=(git_uri,))
    thread.start()

    return jsonify({"message": "Operation started. Check the logs for details."})

@app.route('/logs')
def logs():
    """
    SSE endpoint for streaming log content.
    """
    return Response(stream_logs(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
