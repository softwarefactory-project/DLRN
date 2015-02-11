#!/bin/bash -xe

SCRIPTDIR=$(realpath $(dirname $0))
DISTRO=${1-fedora}

if [ $DISTRO != "rhel" ] ; then
    docker build -t delorean/$DISTRO $SCRIPTDIR/dockerfiles/$DISTRO
else
    # TODO(derekh): handle the rhel case as a Dockerfile
    $SCRIPTDIR/create_rhel_build_image.sh
fi
