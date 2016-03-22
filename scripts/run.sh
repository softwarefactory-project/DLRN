#!/usr/bin/bash

# A simple script to run delorean on a server, continuously
# runs dlrn with a 5 minute sleep between runs.

LOGFILE=dlrn.$(date +%s).log

. ../dlrn-venv/bin/activate

while true; do
    delorean --config-file projects.ini --info-repo /home/rdoinfo/rdoinfo/ --head-only 2>> $LOGFILE
    date
    echo "Sleeping"
    sleep 300
    echo "Awake"
done
