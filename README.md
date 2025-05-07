# BUILDOS Stack

A collection of tools to simplify and automate Yocto build processes:

- **Web application** (Python Flask) with HTML/CSS/JS frontend  
- **Shared volume** hosting mirror assets  
- **Database** for build logs and metadata  
- **Nginx proxy** for routing mirror and webapp requests  

## Table of Contents

- [Overview](#overview)  
- [Prerequisites](#prerequisites)  
- [Setup](#setup)  
    - [1. Git Configuration](#1-git-configuration)  
    - [2. Launching a Build](#2-launching-a-build)  
    - [3. Viewing Build History](#3-viewing-build-history)  
- [Mirror Configuration](#mirror-configuration)  
    - [Local Builds](#local-builds)  
    - [Manual Mirror Upload](#manual-mirror-upload)  
- [Contributing](#contributing)  
- [License](#license)  

## Overview

BUILDOS Stack orchestrates Yocto builds by:

1. Fetching sources into a central mirror  
2. Running bitbake tasks on demand  
3. Archiving build artifacts for download  
4. Providing a web UI for queue management and logs  

## Prerequisites

- A running BUILDOS Stack server (HTTP on port 80)  
- Git repository URI of your Yocto project  
- (Optional) A local clone for manual testing  

## Setup

### 1. Git Configuration

Every repository must include a shell script at `$BASEDIR/.config/mirror.sh`.  
This script initializes your Yocto environment and configures download/mirror paths.

Example `mirror.sh`:
```bash
#!/usr/bin/env bash

# Initialize Yocto build
source poky/oe-init-build-env

LOCAL_CONF="conf/local.conf"

# Ensure download and sstate directories
grep -qxF 'DL_DIR = "/home/generic/yocto-mirror/downloads"' $LOCAL_CONF \
    || echo 'DL_DIR = "/home/generic/yocto-mirror/downloads"' >> $LOCAL_CONF

grep -qxF 'SSTATE_DIR = "${TOPDIR}/sstate-cache"' $LOCAL_CONF \
    || echo 'SSTATE_DIR = "${TOPDIR}/sstate-cache"' >> $LOCAL_CONF

grep -qxF 'SSTATE_MIRRORS = "file://.* file:///home/generic/yocto-mirror/sstate-cache/*"' $LOCAL_CONF \
    || echo 'SSTATE_MIRRORS = "file://.* file:///home/generic/yocto-mirror/sstate-cache/*"' >> $LOCAL_CONF

grep -qxF 'BB_GENERATE_MIRROR_TARBALLS = "1"' $LOCAL_CONF \
    || echo 'BB_GENERATE_MIRROR_TARBALLS = "1"' >> $LOCAL_CONF

# Define your build targets below
bitbake core-image-minimal --runall=fetch

# Output artifacts must go into $BASEDIR/.result/
```

> Note: Run and validate this script once. Subsequent changes should only adjust targets or output paths.

### 2. Launching a Build

1. Open your browser at `http://<SERVER_IP>/`  
2. Paste your Git URI and click **Enqueue New Task**
3. Monitor the **Task Queue** for status updates and check the logs.

In real time you can:

- View logs  
- Cancel or kill a running task  
- Download resulting files from `$BASEDIR/.result/` upon success  

### 3. Viewing Build History

Navigate to **Repository** in the top menu to see all tasks (current and past).  
Click any entry to review logs and download artifacts.

## Mirror Configuration

### Local Builds

To fetch sources from the BUILDOS server and build locally:

1. Perform one initial build on the server to populate the mirror  
2. In your local `conf/local.conf`, add:
     ```conf
     SOURCE_MIRROR_URL = "http://<SERVER_IP>/downloads/"
     SSTATE_MIRRORS    = "file://.* http://<SERVER_IP>/sstate-cache/"
     INHERIT          += "own-mirrors"
     BB_FETCH_PREMIRRORONLY = "1"
     SSTATE_MIRROR_ALLOW_NETWORK = "1"
     CONNECTIVITY_CHECK_URIS = "http://<SERVER_IP>/"
     ```

### Manual Mirror Upload

> WARNING: Manually modifying the mirror can break it. Test locally first.

1. Go to **Mirror manager** in the web UI  
2. Use the file manager to upload tarballs into `downloads/`  
3. (Optional) Upload sstate artifacts into `sstate-cache/` to speed up builds  

Files are served immediately after upload.

## Questions & issues 

Contributions, bug reports, and feature requests are welcome!  
If you discover any issues, contact me at aurelien.izoulet@epita.fr