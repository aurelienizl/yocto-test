#!/bin/bash

# Create directories
mkdir -p pod-mirror/templates

# Create docker-compose.yaml
cat <<EOF > docker-compose.yaml
version: '3'
services:
  mirror:
    build: ./pod-mirror
    volumes:
      - mirror-data:/home/generic/yocto-mirror
    ports:
      - "80:80"

volumes:
  mirror-data:
EOF

# Create pod-mirror/Dockerfile
cat <<EOF > pod-mirror/Dockerfile
FROM ubuntu:20.04

MAINTAINER Aurelien Izoulet <aurelien.izoulet@epita.fr>

ARG DEBIAN_FRONTEND=noninteractive

# Install Yocto build dependencies, Nginx, Python Flask, and Supervisor
RUN \\
    dpkg --add-architecture i386 && \\
    apt-get update && \\
    apt-get install -yq sudo build-essential git nano vim \\
      python3-yaml tmux screen libncursesw5 libncursesw5:i386 \\
      python python3 man bash diffstat gawk chrpath wget cpio \\
      texinfo lzop apt-utils bc screen libncurses5-dev locales \\
      libc6-dev-i386 doxygen libssl-dev dos2unix xvfb x11-utils \\
      g++-multilib libssl-dev:i386 zlib1g-dev:i386 \\
      libtool libtool-bin procps python3-distutils pigz socat \\
      zstd iproute2 lz4 iputils-ping \\
      curl libtinfo5 net-tools xterm rsync u-boot-tools unzip zip \\
      nginx supervisor python3-pip && \\
    pip3 install flask && \\
    rm -rf /var/lib/apt/lists/* && \\
    echo "dash dash/sh boolean false" | debconf-set-selections && \\
    dpkg-reconfigure dash

# Install the repo tool
RUN curl https://storage.googleapis.com/git-repo-downloads/repo > /bin/repo && chmod a+x /bin/repo
RUN sed -i "1s/python/python3/" /bin/repo

# Create the generic group and user with UID/GID 1000
RUN groupadd generic -g 1000 && \\
    useradd -ms /bin/bash -u 1000 -g generic generic && \\
    usermod -aG sudo generic && \\
    echo "generic:generic" | chpasswd

# Set locale
RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \\
    locale-gen
ENV LANG en_US.utf8

WORKDIR /home/generic

# Configure git
RUN git config --global user.email "yocto-build@epita.fr" && git config --global user.name "generic"

# Copy configuration files
COPY nginx.conf /etc/nginx/nginx.conf
COPY app.py /home/generic/app.py
COPY templates /home/generic/templates
COPY build_mirror.sh /home/generic/build_mirror.sh
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Set permissions
RUN chmod +x /home/generic/build_mirror.sh && \\
    chown -R generic:generic /home/generic

# Expose port 80
EXPOSE 80

# Run supervisord to manage Nginx and Flask
CMD ["/usr/bin/supervisord"]
EOF

# Create pod-mirror/nginx.conf
cat <<EOF > pod-mirror/nginx.conf
user generic generic;
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    server {
        listen 80;
        server_name localhost;

        # Serve mirror files
        location /mirror/ {
            alias /home/generic/yocto-mirror/;
            autoindex on;
        }

        # Proxy to Flask app for the web interface
        location / {
            proxy_pass http://127.0.0.1:5000;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
        }
    }
}
EOF

# Create pod-mirror/app.py
cat <<EOF > pod-mirror/app.py
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
EOF

# Create pod-mirror/templates/index.html
cat <<EOF > pod-mirror/templates/index.html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Yocto Mirror Manager</title>
</head>
<body>
    <h1>Yocto Mirror Manager</h1>
    <form method="post">
        <textarea name="projects" rows="10" cols="50">{{ '\n'.join(projects) }}</textarea><br>
        <input type="submit" value="Refresh Mirror">
    </form>
    <p>Access mirror files at <a href="/mirror/">/mirror/</a></p>
</body>
</html>
EOF

# Create pod-mirror/build_mirror.sh
cat <<EOF > pod-mirror/build_mirror.sh
#!/bin/bash

PROJECTS_FILE=/home/generic/projects.txt
MIRROR_DIR=/home/generic/yocto-mirror
TEMP_DIR=/home/generic/temp

# Create temporary directory for cloning
mkdir -p \$TEMP_DIR

# Read each URI from the projects file
while read -r uri; do
    if [ -n "\$uri" ]; then
        repo_name=\$(basename \$uri .git)
        clone_dir=\$TEMP_DIR/\$repo_name
        # Clone the repository
        git clone \$uri \$clone_dir
        if [ -d \$clone_dir/.config ]; then
            cd \$clone_dir/.config
            if [ -f mirror.sh ]; then
                # Execute mirror.sh to populate the mirror
                bash mirror.sh
            fi
            cd -
        fi
        # Clean up temporary clone
        rm -rf \$clone_dir
    fi
done < \$PROJECTS_FILE
EOF

# Make build_mirror.sh executable
chmod +x pod-mirror/build_mirror.sh

# Create pod-mirror/supervisord.conf
cat <<EOF > pod-mirror/supervisord.conf
[supervisord]
nodaemon=true

[program:nginx]
command=nginx -g 'daemon off;'

[program:flask]
command=python3 /home/generic/app.py
user=generic
EOF

echo "Project setup complete."