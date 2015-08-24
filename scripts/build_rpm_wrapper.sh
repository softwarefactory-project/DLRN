#!/bin/bash -xe

DIR=$(realpath $(dirname $0))

if [ "$1" != "openstack-puppet-modules" ] ; then
    $DIR/build_rpm.sh "$@" &> $2/rpmbuild.log
else
    # Special case of the puppet modules as they don't
    # come from a single repo
    $DIR/build_rpm_opm.sh "$@" &> $2/rpmbuild.log
fi
