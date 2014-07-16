#!/bin/bash -xe

mkdir -p ~/rpmbuild/SOURCES ~/rpmbuild/SPECS $3
yum install -y --nogpg python-pip

cd /data/$1
python setup.py sdist
TARBALL=$(ls dist)
VERSION=$(python setup.py --version)
mv dist/$TARBALL ~/rpmbuild/SOURCES/

# The project may have either it's own spec repo of use a subdirectory of the global one
cd /data/$1_spec || cd /data/global_spec/$2
cp * ~/rpmbuild/SOURCES/
cp *.spec ~/rpmbuild/SPECS/
cd ~/rpmbuild/SPECS/


# Add the mostcurrent repo, we may have dependencies in it
if [ -e /data/repos/current ] ; then
    echo -e '[current]\nname=current\nbaseurl=file:///data/repos/current\nenabled=1\ngpgcheck=0' > /etc/yum.repos.d/current.repo
fi

sed -i -e "s/VERSIONDIR/$VERSION/g" *.spec
VERSION=${VERSION/-/.}
sed -i -e "s/Version:.*/Version: $VERSION/g" *.spec
sed -i -e "s/Source0:.*/Source0: $TARBALL/g" *.spec
yum-builddep -y *.spec
rpmbuild -ba *.spec
find /rpmbuild/RPMS /rpmbuild/SRPMS -type f | xargs cp -t $3

yum install -y --nogpg $(find $3 -name "*rpm" | grep -v src.rpm) && touch $3/installed || true
