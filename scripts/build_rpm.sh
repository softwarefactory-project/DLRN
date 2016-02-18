#!/bin/bash -xe

set -o pipefail

source $(dirname $0)/common-functions

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

RPM_CHANGELOG=$(/usr/bin/mock -q -r ${DATA_DIR}/delorean.cfg --chroot "cd /tmp/pkgsrc && git log -n 25 --oneline")

# https://bugs.launchpad.net/tripleo/+bug/1351491
if [[ "$PROJECT_NAME" =~  ^(diskimage-builder|tripleo-heat-templates|tripleo-image-elements)$ ]] ; then
    if [ "$VERSION" == "0.0.1" ] ; then
        VERSION=$(git tag | sort -V | tail -n 1)
   fi
fi

mv dist/$TARBALL ${TOP_DIR}/SOURCES/

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
RPM_DATE=$(LC_TIME=C date -u +"%a %b %d %Y")
echo "* ${RPM_DATE} delorean <delorean@rdoproject.org> ${VERSION}-${RELEASE}" >> *.spec
printf "%s" "${RPM_CHANGELOG%x}" >> *.spec
cat *.spec
rpmbuild --define="_topdir ${TOP_DIR}" -bs ${TOP_DIR}/SPECS/*.spec
/usr/bin/mock $MOCKOPTS --postinstall --rebuild ${TOP_DIR}/SRPMS/*.src.rpm 2>&1 | tee $OUTPUT_DIRECTORY/mock.log

if ! grep -F 'WARNING: Failed install built packages' $OUTPUT_DIRECTORY/mock.log; then
    touch $OUTPUT_DIRECTORY/installed
fi
