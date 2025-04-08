import os
import subprocess
from flask import Flask, request, render_template, jsonify

# Define constants (adjust paths as needed)
LOG_FILE = '/home/generic/build_mirror.log'
TEMP_DIR = '/home/generic/temp'

app = Flask(__name__, template_folder='/home/generic/templates')

class GitMirrorRunner:
    """
    A class to clone a Git repository, execute the mirror script if available,
    and then clean up.
    """
    def __init__(self, git_uri, temp_dir=TEMP_DIR, log_file=LOG_FILE):
        self.git_uri = git_uri
        self.temp_dir = temp_dir
        self.log_file = log_file
        
        # Extract repository name from URI, stripping '.git' if needed
        self.repo_name = os.path.basename(git_uri)
        if self.repo_name.endswith('.git'):
            self.repo_name = self.repo_name[:-4]
        self.clone_dir = os.path.join(self.temp_dir, self.repo_name)

    def _log(self, message):
        """
        Log a message to the log file and print it to the console.
        """
        with open(self.log_file, 'a') as f:
            f.write(message + "\n")
        print(message)

    def run(self):
        """
        Clone the repository, run the mirror script if it exists, and clean up.
        """
        # Ensure the temporary directory exists
        os.makedirs(self.temp_dir, exist_ok=True)

        self._log(f"Cloning {self.git_uri} into {self.clone_dir}")
        try:
            with open(self.log_file, 'a') as log_f:
                subprocess.run(
                    ["git", "clone", self.git_uri, self.clone_dir],
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    check=True
                )
        except subprocess.CalledProcessError as e:
            self._log(f"Error cloning {self.git_uri}: {e}")
            return False

        # Define the expected path of the mirror script: .config/mirror.sh in the repository root.
        script_path = os.path.join(self.clone_dir, ".config", "mirror.sh")
        if os.path.isfile(script_path):
            self._log(f"Executing script {script_path}")
            try:
                with open(self.log_file, 'a') as log_f:
                    subprocess.run(
                        ["bash", script_path],
                        cwd=self.clone_dir,  # set working directory to repository root
                        stdout=log_f,
                        stderr=subprocess.STDOUT,
                        check=True
                    )
            except subprocess.CalledProcessError as e:
                self._log(f"Error executing script {script_path}: {e}")
        else:
            self._log(f"No mirror script found at {script_path}")

        # Clean up the temporary clone
        self._log(f"Cleaning up clone at {self.clone_dir}")
        try:
            subprocess.run(
                ["rm", "-rf", self.clone_dir],
                check=True
            )
        except subprocess.CalledProcessError as e:
            self._log(f"Error cleaning up {self.clone_dir}: {e}")
        return True

# Flask endpoints

@app.route('/', methods=['GET'])
def index():
    """
    Render a single‑page interface for entering a Git URI.
    """
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run_git():
    """
    Accept a Git URI via POST, execute the mirror process using GitMirrorRunner,
    and return a JSON response.
    """
    git_uri = request.form.get('git_uri', '').strip()
    if not git_uri:
        return jsonify({"error": "No Git URI provided"}), 400
    
    runner = GitMirrorRunner(git_uri)
    success = runner.run()
    if success:
        return jsonify({"message": "Process completed successfully."})
    else:
        return jsonify({"error": "Process encountered errors."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
