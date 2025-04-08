source poky/oe-init-build-env

### Setting up the configuration ###

# We add thoses lines in the local.conf file ##
# DL_DIR = "/home/generic/yocto-mirror/downloads"
# SSTATE_DIR = "/home/generic/yocto-mirror/sstate-cache"
# BB_GENERATE_MIRROR_TARBALLS = "1"

# Add lines to the local.conf file if they don't already exist
LOCAL_CONF="conf/local.conf"

grep -qxF 'DL_DIR = "/home/generic/yocto-mirror/downloads"' $LOCAL_CONF || echo 'DL_DIR = "/home/generic/yocto-mirror/downloads"' >> $LOCAL_CONF
grep -qxF 'SSTATE_DIR = "/home/generic/yocto-mirror/sstate-cache"' $LOCAL_CONF || echo 'SSTATE_DIR = "/home/generic/yocto-mirror/sstate-cache"' >> $LOCAL_CONF
grep -qxF 'BB_GENERATE_MIRROR_TARBALLS = "1"' $LOCAL_CONF || echo 'BB_GENERATE_MIRROR_TARBALLS = "1"' >> $LOCAL_CONF


### Your targets must be runned here ###

bitbake core-image-minimal

### End of your tagets ###