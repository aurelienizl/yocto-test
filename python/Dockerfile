# syntax=docker/dockerfile:1
FROM python:3.9-slim AS base

# Set environment variables for performance and consistency
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=en_US.UTF-8 \
    DEBIAN_FRONTEND=noninteractive

# Metadata labels for enterprise-grade images
LABEL org.opencontainers.image.authors="aurelien.izoulet@epita.fr" \
      org.opencontainers.image.title="Yocto Build & Flask App" \
      org.opencontainers.image.description="An enterprise-grade container running a Yocto build environment and a Flask-based mirror controller" \
      org.opencontainers.image.version="1.0"

##############################################################
#                                                            #
#  Install dependencies for the Yocto build and Flask app    #
#                                                            #
##############################################################
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        sudo \
        build-essential \
        git \
        nano \
        vim \
        python3-yaml \
        tmux \
        screen \
        libncursesw5 \
        libncursesw5:i386 \
        python-is-python3 \
        python3 \
        man \
        bash \
        diffstat \
        gawk \
        chrpath \
        wget \
        cpio \
        texinfo \
        lzop \
        apt-utils \
        bc \
        libncurses5-dev \
        locales \
        libc6-dev-i386 \
        doxygen \
        libssl-dev \
        dos2unix \
        xvfb \
        x11-utils \
        g++-multilib \
        libssl-dev:i386 \
        zlib1g-dev:i386 \
        libtool \
        libtool-bin \
        procps \
        python3-distutils \
        pigz \
        socat \
        zstd \
        iproute2 \
        lz4 \
        iputils-ping \
        curl \
        libtinfo5 \
        net-tools \
        xterm \
        rsync \
        u-boot-tools \
        unzip \
        zip \
        nginx \
        supervisor \
        python3-pip && \
    # Install Flask via pip (pin version as needed)
    pip3 install --no-cache-dir flask && \
    rm -rf /var/lib/apt/lists/* && \
    echo "dash dash/sh boolean false" | debconf-set-selections && \
    dpkg-reconfigure dash

# Install the repo tool into /usr/local/bin and enforce Python3
RUN curl -fsSL https://storage.googleapis.com/git-repo-downloads/repo -o /usr/local/bin/repo && \
    chmod a+x /usr/local/bin/repo && \
    sed -i "1s/python/python3/" /usr/local/bin/repo

#################################################################
#                                                               #
#          Setup non-root user and environment                #
#                                                               #
#################################################################
# Create a non-root user and group with UID/GID 1000
RUN groupadd --gid 1000 generic && \
    useradd --uid 1000 --gid generic --create-home generic && \
    usermod -aG sudo generic && \
    echo "generic:generic" | chpasswd

# Generate locale settings
RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen

# Set working directory and copy application files with proper ownership
WORKDIR /home/generic
COPY --chown=generic:generic app.py /home/generic/app.py
COPY --chown=generic:generic mirror.py /home/generic/mirror.py
COPY --chown=generic:generic templates /home/generic/templates
COPY --chown=generic:generic static /home/generic/static

# Create Yocto mirror directories (for downloads and sstate-cache)
RUN mkdir -p /home/generic/yocto-mirror/downloads /home/generic/yocto-mirror/sstate-cache && \
    chown -R generic:generic /home/generic/yocto-mirror

# Switch to the non-root user
USER generic

# Expose the port the Flask app runs on
EXPOSE 5000

# Define a healthcheck to monitor container status
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD curl --fail http://localhost:5000/ || exit 1

# Use exec form to run the Flask app
ENTRYPOINT ["python"]
CMD ["app.py"]
