FROM ubuntu:20.04

MAINTAINER Aurelien Izoulet <aurelien.izoulet@epita.fr>

ARG DEBIAN_FRONTEND=noninteractive

# Install Yocto build dependencies, Nginx, Python Flask, and Supervisor
RUN \
    dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -yq sudo build-essential git nano vim \
      python3-yaml tmux screen libncursesw5 libncursesw5:i386 \
      python python3 man bash diffstat gawk chrpath wget cpio \
      texinfo lzop apt-utils bc screen libncurses5-dev locales \
      libc6-dev-i386 doxygen libssl-dev dos2unix xvfb x11-utils \
      g++-multilib libssl-dev:i386 zlib1g-dev:i386 \
      libtool libtool-bin procps python3-distutils pigz socat \
      zstd iproute2 lz4 iputils-ping \
      curl libtinfo5 net-tools xterm rsync u-boot-tools unzip zip \
      nginx supervisor python3-pip && \
    pip3 install flask && \
    rm -rf /var/lib/apt/lists/* && \
    echo "dash dash/sh boolean false" | debconf-set-selections && \
    dpkg-reconfigure dash

# Install the repo tool
RUN curl https://storage.googleapis.com/git-repo-downloads/repo > /bin/repo && chmod a+x /bin/repo
RUN sed -i "1s/python/python3/" /bin/repo

# Create the generic group and user with UID/GID 1000
RUN groupadd generic -g 1000 && \
    useradd -ms /bin/bash -u 1000 -g generic generic && \
    usermod -aG sudo generic && \
    echo "generic:generic" | chpasswd

# Set locale
RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
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
RUN chmod +x /home/generic/build_mirror.sh && \
    chown -R generic:generic /home/generic

# Expose port 80
EXPOSE 80

# Run supervisord to manage Nginx and Flask
CMD ["/usr/bin/supervisord"]
