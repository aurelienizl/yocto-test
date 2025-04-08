#!/bin/bash

PROJECTS_FILE=/home/generic/projects.txt
MIRROR_DIR=/home/generic/yocto-mirror
TEMP_DIR=/home/generic/temp

# Create temporary directory for cloning
mkdir -p $TEMP_DIR

# Read each URI from the projects file
while read -r uri; do
    if [ -n "$uri" ]; then
        repo_name=$(basename $uri .git)
        clone_dir=$TEMP_DIR/$repo_name
        # Clone the repository
        git clone $uri $clone_dir
        if [ -d $clone_dir/.config ]; then
            cd $clone_dir/.config
            if [ -f mirror.sh ]; then
                # Execute mirror.sh to populate the mirror
                bash mirror.sh
            fi
            cd -
        fi
        # Clean up temporary clone
        rm -rf $clone_dir
    fi
done < $PROJECTS_FILE
