from flask import Flask, request, render_template
import subprocess
import os

app = Flask(__name__, template_folder='/home/generic/templates')

PROJECTS_FILE = '/home/generic/projects.txt'
MIRROR_DIR = '/home/generic/yocto-mirror'

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
