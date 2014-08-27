#!/bin/bash -xe

if [ "$1" != "openstack-puppet-modules" ] ; then
    /scripts/build_rpm.sh $@ &> $3/rpmbuild.log
else
    # Special case of the puppet modules as they don't
    # come from a single repo
    /scripts/build_rpm_opm.sh $@ &> $3/rpmbuild.log
fi
