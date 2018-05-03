#!/bin/bash -e
#
# Copyright (C) 2016 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

set -o pipefail

source $(dirname $0)/common-functions

exec > $OUTPUT_DIRECTORY/review.log 2>&1

set -x

if [ -n "$GERRIT_URL" -a -n "$GERRIT_LOG" -a -n "$GERRIT_MAINTAINERS" -a -n "$GERRIT_TOPIC" ]; then
    cd ${DATA_DIR}/${PROJECT_NAME}
    LONGSHA1=$(git rev-parse HEAD)
    SHORTSHA1=$(git rev-parse --short HEAD)
    cd ${DISTGIT_DIR}
    CURBRANCH=$(git rev-parse --abbrev-ref HEAD)
    git branch -D branch-$SHORTSHA1 || true
    git checkout -b branch-$SHORTSHA1
    git review -s
    # we need to inject a pseudo-modification to the spec file to have a
    # change to commit
    sed -i -e "\$a\\# REMOVEME: error caused by commit ${GERRIT_URL}\\" *.spec
    echo -e "${PROJECT_NAME}: failed to build ${SHORTSHA1}\n\nNeed to fix build error caused by ${GERRIT_URL}\nSee log at ${GERRIT_LOG}"|git commit -F- *.spec
    CHID=$(git log -1|grep -F Change-Id: |cut -d':' -f2)
    MAINTAINERS="${GERRIT_MAINTAINERS//,/ -a }"
    REMOTE=$(git remote show -n gerrit|grep -F 'Fetch URL'|sed 's/.*: //')
    # extract the component from the remote git repository
    # the url should be in this form: ssh://<username>@<server>:<port>/<path>
    REMOTE_HOST=$(echo $REMOTE|cut -d/ -f3|cut -d: -f1)
    REMOTE_PORT=$(echo $REMOTE|cut -d/ -f3|cut -d: -f2)
    PROJECT=$(echo $REMOTE|sed 's@.*://@@'|sed 's@[^/]*/\(.*\)$@\1@')
    git review -t ${GERRIT_TOPIC} < /dev/null
    ssh -p $REMOTE_PORT $REMOTE_HOST gerrit set-reviewers --project $PROJECT -a $MAINTAINERS -- $CHID
    git checkout ${CURBRANCH:-master}
else
    echo "No gerrit review to create"
fi

# submit_review.sh ends here
