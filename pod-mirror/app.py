from flask import Flask, request, render_template, Response
import subprocess
import os
import time

app = Flask(__name__, template_folder='/home/generic/templates')

PROJECTS_FILE = '/home/generic/projects.txt'
MIRROR_DIR = '/home/generic/yocto-mirror'
LOG_FILE = '/home/generic/build_mirror.log'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Save the list of project URIs from the form
        projects = request.form.get('projects', '').splitlines()
        with open(PROJECTS_FILE, 'w') as f:
            for project in projects:
                f.write(project.strip() + '\n')
        # Trigger the build process in the background
        subprocess.Popen(['bash', '/home/generic/build_mirror.sh'])
        return 'Mirror refresh started. This may take a while.'
    else:
        # Load existing projects if the file exists
        if os.path.exists(PROJECTS_FILE):
            with open(PROJECTS_FILE, 'r') as f:
                projects = f.read().splitlines()
        else:
            projects = []
        return render_template('index.html', projects=projects)

def stream_logs():
    """Generator function that yields new lines in the log file using SSE format."""
    # Ensure the file exists
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, 'w').close()
    with open(LOG_FILE, 'r') as f:
        # Go to the end of the file
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                # SSE requires the data field to be prefixed by 'data: '
                yield f"data: {line.strip()}\n\n"
            else:
                time.sleep(1)

@app.route('/logs')
def logs():
    # Return a streaming response using the SSE MIME type
    return Response(stream_logs(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
