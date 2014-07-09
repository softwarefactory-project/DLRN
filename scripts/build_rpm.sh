#!/bin/bash -xe

mkdir -p ~/rpmbuild/SOURCES ~/rpmbuild/SPECS $3
yum install -y --nogpg python-pip

cd /data/$1
python setup.py sdist
TARBALL=$(ls dist)
mv dist/$TARBALL ~/rpmbuild/SOURCES/

# The project may have either it's own spec repo of use a subdirectory of the global one
cd /data/$1_spec || cd /data/global_spec/$2
cp * ~/rpmbuild/SOURCES/
cp *.spec ~/rpmbuild/SPECS/
cd ~/rpmbuild/SPECS/

VERSION=${TARBALL%%.tar*}
VERSION=${VERSION//*-}

# Add the mostcurrent repo, we may have dependencies in it
echo -e '[current]\nname=current\nbaseurl=file:///data/repos/current\nenabled=1\ngpgcheck=0' > /etc/yum.repos.d/current.repo

sed -i -e "s/Version:.*/Version: $VERSION/g" *.spec
sed -i -e "s/Source0:.*/Source0: $TARBALL/g" *.spec
yum-builddep -y *.spec
rpmbuild -ba *.spec
find /rpmbuild/RPMS /rpmbuild/SRPMS -type f | xargs cp -t $3
