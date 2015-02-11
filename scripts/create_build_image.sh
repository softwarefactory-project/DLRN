#!/bin/bash -xe

SCRIPTDIR=$(realpath $(dirname $0))


docker rm build_image || true
docker run -i --volume=$SCRIPTDIR:/scripts --name build_image fedora /scripts/update_image.sh
docker rmi delorean/fedora || true
docker commit build_image delorean/fedora
docker rm build_image
