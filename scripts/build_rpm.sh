#!/bin/bash -xe

mkdir -p ~/rpmbuild/SOURCES ~/rpmbuild/SPECS $3
yum install -y --nogpg python-pip

cd /data/$1
rm -f dist/*
python setup.py sdist
TARBALL=$(ls dist)
UPSTREAMVERSION=$(python setup.py --version)
# version-release e.g 1.0.0-d7f1b849
if [[ "$UPSTREAMVERSION" =~ (.*?)-(.+) ]] ; then
    VERSION=${BASH_REMATCH[1]}
    RELEASE=${BASH_REMATCH[2]}
# 2014.2.dev50.g99bef1f
elif [[ "$UPSTREAMVERSION" =~ (.*?)\.(dev.+) ]] ; then
    VERSION=${BASH_REMATCH[1]}
    RELEASE=${BASH_REMATCH[2]}
# 0.10.1.11.ga5f0e3c
elif [[ "$UPSTREAMVERSION" =~ (.*?)\.(g.+) ]] ; then
    VERSION=${BASH_REMATCH[1]}
    RELEASE=${BASH_REMATCH[2]}
# Only version e.g. 1.7.3
elif [[ "$UPSTREAMVERSION" =~ ^([.0-9]*)$ ]] ; then
    VERSION=${BASH_REMATCH[1]}
    RELEASE=1
    # python-alembic version=0.6.6 but tarball is 0.6.6dev
    if [[ "$TARBALL" =~ dev\.t ]] ; then
        UPSTREAMVERSION=${UPSTREAMVERSION}dev
    fi
# 2.2.0.0a3
elif [[ "$UPSTREAMVERSION" =~ (.*?)\.(.+) ]] ; then
    VERSION=${BASH_REMATCH[1]}
    RELEASE=${BASH_REMATCH[2]}
else
    # e.g. eb6dbe2
    echo  "ERROR : Couldn't parse VERSION, falling back to 0.0.1"
    VERSION=0.0.1
    RELEASE=$UPSTREAMVERSION
fi

# https://bugs.launchpad.net/tripleo/+bug/1351491
if [[ "$1" =~  ^(diskimage-builder|openstack-tripleo|openstack-tripleo-heat-templates|openstack-tripleo-image-elements)$ ]] ; then
    if [ "$VERSION" == "0.0.1" ] ; then
        $VERSION=$(git tag | sort -V | tail -n 1)
   fi
fi

mv dist/$TARBALL ~/rpmbuild/SOURCES/

# The project may have either it's own spec repo of use a subdirectory of the global one
cd /data/$1_spec || cd /data/global_spec/$2
cp * ~/rpmbuild/SOURCES/
cp *.spec ~/rpmbuild/SPECS/
cd ~/rpmbuild/SPECS/


# Add the mostcurrent repo, we may have dependencies in it
if [ -e /data/repos/current/repodata ] ; then
    echo -e '[current]\nname=current\nbaseurl=file:///data/repos/current\nenabled=1\ngpgcheck=0' > /etc/yum.repos.d/current.repo
fi

sed -i -e "s/UPSTREAMVERSION/$UPSTREAMVERSION/g" *.spec
VERSION=${VERSION/-/.}
sed -i -e "s/Version:.*/Version: $VERSION/g" *.spec
sed -i -e "s/Release:.*/Release: $RELEASE%{?dist}/g" *.spec
sed -i -e "s/Source0:.*/Source0: $TARBALL/g" *.spec
cat *.spec
yum-builddep -y *.spec
rpmbuild -ba *.spec  --define="upstream_version $UPSTREAMVERSION"
find /rpmbuild/RPMS /rpmbuild/SRPMS -type f | xargs cp -t $3

yum install -y --nogpg $(find $3 -name "*rpm" | grep -v src.rpm) && touch $3/installed || true
