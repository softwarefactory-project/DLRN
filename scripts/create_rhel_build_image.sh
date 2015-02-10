#!/bin/bash -xe

SCRIPTDIR=$(realpath $(dirname $0))
REG_POOL_ID=${REG_POOL_ID:-}

docker rm build_image || true
docker run -t -i --volume=$SCRIPTDIR:/scripts --name build_image -e "REG_POOL_ID=${REG_POOL_ID}" rhel /scripts/update_rhel_image.sh
docker rmi delorean/rhel || true
docker commit build_image delorean/rhel
docker rm build_image
