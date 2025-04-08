#!/bin/bash

LOG_FILE=/home/generic/build_mirror.log
PROJECTS_FILE=/home/generic/projects.txt
MIRROR_DIR=/home/generic/yocto-mirror
TEMP_DIR=/home/generic/temp

# Clean or create the log file
: > $LOG_FILE

# Create temporary directory for cloning
mkdir -p $TEMP_DIR

# Read each URI from the projects file
while read -r uri; do
    if [ -n "$uri" ]; then
        repo_name=$(basename "$uri" .git)
        clone_dir=$TEMP_DIR/$repo_name
        echo "Cloning $uri into $clone_dir" >> $LOG_FILE
        # Clone the repository and log output
        git clone "$uri" "$clone_dir" >> $LOG_FILE 2>&1
        if [ -f "$clone_dir/mirror.sh" ]; then
            echo "Running mirror.sh in $clone_dir" >> $LOG_FILE
            cd "$clone_dir" || continue
            bash mirror.sh >> $LOG_FILE 2>&1
            cd - >> $LOG_FILE 2>&1
        fi
        # Clean up temporary clone
        rm -rf "$clone_dir"
    fi
done < "$PROJECTS_FILE"
