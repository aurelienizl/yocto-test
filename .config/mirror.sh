#!/bin/bash
source poky/oe-init-build-env

### Setting up the configuration ###

# Add lines to the local.conf file if they don't already exist
LOCAL_CONF="conf/local.conf"

grep -qxF 'DL_DIR = "/home/generic/yocto-mirror/downloads"' $LOCAL_CONF || echo 'DL_DIR = "/home/generic/yocto-mirror/downloads"' >> $LOCAL_CONF
grep -qxF 'SSTATE_DIR = "${TOPDIR}/sstate-cache"' $LOCAL_CONF || echo 'SSTATE_DIR = "${TOPDIR}/sstate-cache"' >> $LOCAL_CONF
grep -qxF 'SSTATE_MIRRORS = "file://.* file:///home/generic/yocto-mirror/sstate-cache/*"' $LOCAL_CONF || echo 'SSTATE_MIRRORS = "file://.* file:///home/generic/yocto-mirror/sstate-cache/*"' >> $LOCAL_CONF
grep -qxF 'BB_GENERATE_MIRROR_TARBALLS = "1"' $LOCAL_CONF || echo 'BB_GENERATE_MIRROR_TARBALLS = "1"' >> $LOCAL_CONF

### Your targets must be run here ###

bitbake core-image-minimal --runall=fetch