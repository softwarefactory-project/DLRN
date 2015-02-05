#!/bin/bash -xe

subscription-manager unregister || true
subscription-manager clean || true
subscription-manager register

REG_POOL_ID=${REG_POOL_ID:-}
if [ -z "$REG_POOL_ID" ]; then
    echo -n "Pool id: "
    read REG_POOL_ID
fi
subscription-manager attach --pool=$REG_POOL_ID

subscription-manager repos --list | grep -B 3 'Enabled:   1' | grep 'Repo ID:   ' | awk '{print $3}' | while read r; do
    subscription-manager repos --disable $r
done
subscription-manager repos --enable rhel-7-server-extras-rpms --enable rhel-7-server-rpms --enable rhel-7-server-rh-common-rpms --enable rhel-7-server-optional-rpms

rpm -ivh http://dl.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-5.noarch.rpm
yum update -y --nogpg
yum install -y --nogpg rpm-build git python-setuptools yum-utils python2-devel intltool make python-pip gcc yum-plugin-priorities
# temp deps
yum install -y --nogpg python-sqlalchemy python-webob python-eventlet ghostscript graphviz python-sphinx
