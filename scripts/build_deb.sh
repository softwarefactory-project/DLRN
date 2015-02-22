#!/bin/bash -xe

PROJECT_NAME=$1
OUTPUT_DIRECTORY=$2
USER_ID=$3 # chown resulting files to this UID
GROUP_ID=$4 # chown resulting files to this GUID

mkdir -p $OUTPUT_DIRECTORY
apt-get install -y python-pip python-pbr

cd /data/$PROJECT_NAME
rm -f dist/*
python setup.py sdist
TARBALL=$(ls dist)
# setup.py outputs warning (to stdout) in some cases (python-posix_ipc)
# so only look at the last line for version
UPSTREAMVERSION=$(python setup.py --version | tail -n 1)
UPSTREAMVERSION=$(echo $UPSTREAMVERSION | sed -e 's/.g/~g/')
VERSION="${UPSTREAMVERSION}-1"

mv dist/$TARBALL /data

rm -rf /data/${PROJECT_NAME}/debian
mv /data/${PROJECT_NAME}_distro/debian /data/${PROJECT_NAME}/

# Grab Source field out of the control file, it may not be the same as the
# project name.
SRC_PKG_NAME=$(grep '^Source: ' /data/${PROJECT_NAME}/debian/control | cut -d\  -f2)
ln -sfn $TARBALL ../${SRC_PKG_NAME}_${UPSTREAMVERSION}.orig.tar.gz

# We may need an epoch to be larger than the version shipped.
EPOCH=
CURRENT_VERSION=$(dpkg-parsechangelog --show-field Version)
case "$CURRENT_VERSION" in
    *:*)
        EPOCH=$(echo $CURRENT_VERSION | cut -d: -f1)
        ;;
esac
if [ -n "$EPOCH" ]; then
    VERSION="$EPOCH:$VERSION"
fi

# Add the current repo if it exists.
if [ -e /data/repos/current/Packages.gz ]; then
    echo -e 'deb file:///data/repos/current ./\ndeb-src file:///data/repos/current ./\n' > /etc/apt/sources.list.d/current.list
    apt-get update
fi

export DEBFULLNAME="Delorean"
export DEBEMAIL="delorean@example.com"
export DEBIAN_FRONTEND="noninteractive"
dch -v "$VERSION" --distribution trusty --package "$SRC_PKG_NAME" \
    "Automatically generated build for Trusty."
rm -f ${SRC_PKG_NAME}*build-deps*deb
mk-build-deps debian/control
# Using gdebi here, because using apt-get with mk-build-deps can end up with
# apt's dependency resolver deciding the best course of action is not
# installing the build-deps package because of broken dependencies.
gdebi --n ${SRC_PKG_NAME}*build-deps*deb
dpkg-buildpackage -i.*
cd ..
for file in $(find . -mindepth 1 -maxdepth 1 -type f -o -type l); do
    cp -d $file $OUTPUT_DIRECTORY
done

if [ -s ${PROJECT_NAME}/debian/files ]; then
    # And using dpkg -i here, since gdebi does not deal with the case that a
    # required dependency is specified later in the same command line.
    set +e
    dpkg -i $(cut -d' ' -f1 < ${PROJECT_NAME}/debian/files)
    set -e
    # But we still want to know if other dependencies can not be installed.
    apt-get -fy install
    touch $OUTPUT_DIRECTORY/installed
fi

chown -R $USER_ID:$GROUP_ID $OUTPUT_DIRECTORY
