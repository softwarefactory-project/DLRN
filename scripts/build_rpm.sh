#!/bin/bash -xe

set -o pipefail

source $(dirname $0)/common-functions

function build_failure() {
    if [ -n "$GERRIT" -a -n "$GERRIT_LOG" ]; then
        echo "Creating a gerrit review"
        cd ${DATA_DIR}/${PROJECT_NAME}_distro
        CURBRANCH=$(git rev-parse --abbrev-ref HEAD)
        git checkout -b branch-$SHORTSHA1
        # we need to inject a pseudo-modification to the spec file to have a
        # change to commit
        sed -i -e "\$a\\# REMOVEME: error caused by commit $GERRIT\\" *.spec
        echo -e "Need to fix build error caused by $GERRIT\n\nSee log at $GERRIT_LOG"|git commit -F- *.spec
        git review
        git checkout ${CURBRANCH:-master}
    else
        echo "No gerrit review to create"
    fi
    exit 1
}

for FILE in {test-,}requirements.txt
do
    if [ -f ${FILE} ]
    then
        sed -i "s/;python_version[!=<>]=\?.*//g" ${FILE}
        sed -i "s/;sys_platform[!=<>]=\?.*//g" ${FILE}
    fi
done

cleanup_sdist

MOCKOPTS="-v -r ${DATA_DIR}/delorean.cfg --resultdir $OUTPUT_DIRECTORY"

# Cleanup mock directory and copy sources there, so we can run python setup.py
# inside the buildroot
/usr/bin/mock $MOCKOPTS --clean
/usr/bin/mock $MOCKOPTS --init
# A simple mock --copyin should be enough, but it does not handle symlinks properly
MOCKDIR=$(/usr/bin/mock -r ${DATA_DIR}/delorean.cfg -p)
mkdir ${MOCKDIR}/tmp/pkgsrc
cp -pr . ${MOCKDIR}/tmp/pkgsrc
/usr/bin/mock $MOCKOPTS --chroot "cd /tmp/pkgsrc && python setup.py sdist"
/usr/bin/mock $MOCKOPTS --copyout /tmp/pkgsrc/dist ./dist
TARBALL=$(ls dist)

# setup.py outputs warning (to stdout) in some cases (python-posix_ipc)
# so only look at the last line for version
setversionandrelease $(/usr/bin/mock -q -r ${DATA_DIR}/delorean.cfg --chroot "cd /tmp/pkgsrc && python setup.py --version"| tail -n 1) \
                     $(/usr/bin/mock -q -r ${DATA_DIR}/delorean.cfg --chroot "cd /tmp/pkgsrc && git log -n1 --format=format:%h")

# https://bugs.launchpad.net/tripleo/+bug/1351491
if [[ "$PROJECT_NAME" =~  ^(diskimage-builder|tripleo-heat-templates|tripleo-image-elements)$ ]] ; then
    if [ "$VERSION" == "0.0.1" ] ; then
        VERSION=$(git tag | sort -V | tail -n 1)
    fi
fi

mv dist/$TARBALL ${TOP_DIR}/SOURCES/
LONGSHA1=$(git rev-parse HEAD)
SHORTSHA1=$(git rev-parse --short HEAD)

cd ${DATA_DIR}/${PROJECT_NAME}_distro
cp * ${TOP_DIR}/SOURCES/
cp *.spec ${TOP_DIR}/SPECS/
cd ${TOP_DIR}/SPECS/

sed -i -e "1i%define upstream_version $UPSTREAMVERSION\\" *.spec
sed -i -e "s/UPSTREAMVERSION/$UPSTREAMVERSION/g" *.spec
VERSION=${VERSION/-/.}
sed -i -e "s/Version:.*/Version: $VERSION/g" *.spec
sed -i -e "s/Release:.*/Release: $RELEASE%{?dist}/g" *.spec
sed -i -e "s/Source0:.*/Source0: $TARBALL/g" *.spec
cat *.spec
rpmbuild --define="_topdir ${TOP_DIR}" -bs ${TOP_DIR}/SPECS/*.spec

if /usr/bin/mock $MOCKOPTS --postinstall --rebuild ${TOP_DIR}/SRPMS/*.src.rpm 2>&1 | tee $OUTPUT_DIRECTORY/mock.log; then
    if ! grep -F 'WARNING: Failed install built packages' $OUTPUT_DIRECTORY/mock.log; then
        touch $OUTPUT_DIRECTORY/installed
    else
        build_failure
    fi
else
    build_failure
fi
