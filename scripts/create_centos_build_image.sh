#!/bin/bash -xe

SCRIPTDIR=$(realpath $(dirname $0))


docker rm build_image || true
docker run -t -i --volume=$SCRIPTDIR:/scripts --name build_image centos /scripts/update_centos_image.sh
docker rmi delorean/centos || true
docker commit build_image delorean/centos
docker rm build_image
