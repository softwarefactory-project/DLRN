#!/bin/bash -xe

mkdir -p ~/rpmbuild/SOURCES ~/rpmbuild/SPECS $2
yum install -y --nogpg python-pip

sleep 3
cd /data/$1
python setup.py sdist
TARBALL=$(ls dist/* | grep -Eo "$1.*") 
mv dist/$TARBALL ~/rpmbuild/SOURCES/

cd /data/$1_spec
cp * ~/rpmbuild/SOURCES/
cp openstack-$1.spec ~/rpmbuild/SPECS/
cd ~/rpmbuild/SPECS/

VERSION=${TARBALL%%.tar*}
VERSION=${VERSION//*-}

sed -i -e "s/Version:.*/Version: $VERSION/g" openstack-$1.spec
sed -i -e "s/Source0:.*/Source0: $TARBALL/g" openstack-$1.spec
yum-builddep -y openstack-$1.spec
rpmbuild -ba openstack-$1.spec &> $2/rpmbuild.log
find /rpmbuild/RPMS /rpmbuild/SRPMS -type f | xargs cp -t $2
