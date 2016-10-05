#!/bin/bash -xe

set -o pipefail

shift   # First parameter is TARGET, not needed here

source $(dirname $0)/common-functions

exec &> >(tee "${OUTPUT_DIRECTORY}/rpmbuild.log") 2>&1
set -x

for FILE in {test-,}requirements.txt
do
    if [ -f ${FILE} ]
    then
        sed -i "s/; *python_version.*[!=<>]=\?.*//g" ${FILE}
        sed -i "s/; *sys_platform.*[!=<>]=\?.*//g" ${FILE}
    fi
done

cleanup_sdist

MOCKOPTS="-v -r ${DATA_DIR}/${MOCK_CONFIG} --resultdir $OUTPUT_DIRECTORY"

# Cleanup mock directory and copy sources there, so we can run python setup.py
# inside the buildroot
/usr/bin/mock $MOCKOPTS --clean
/usr/bin/mock $MOCKOPTS --init
# A simple mock --copyin should be enough, but it does not handle symlinks properly
MOCKDIR=$(/usr/bin/mock -r ${DATA_DIR}/${MOCK_CONFIG} -p)

# handle python packages (some puppet modules are carrying a setup.py too)
if [ -r setup.py -a ! -r metadata.json ]; then
    mkdir ${MOCKDIR}/tmp/pkgsrc
    cp -pr . ${MOCKDIR}/tmp/pkgsrc
    /usr/bin/mock $MOCKOPTS --chroot "cd /tmp/pkgsrc && python setup.py sdist"
    /usr/bin/mock $MOCKOPTS --copyout /tmp/pkgsrc/dist ./dist

    # setup.py outputs warning (to stdout) in some cases (python-posix_ipc)
    # so only look at the last line for version
    setversionandrelease $(/usr/bin/mock -q -r ${DATA_DIR}/${MOCK_CONFIG} --chroot "cd /tmp/pkgsrc && python setup.py --version"| tail -n 1) \
                         $(/usr/bin/mock -q -r ${DATA_DIR}/${MOCK_CONFIG} --chroot "cd /tmp/pkgsrc && git log -n1 --format=format:%h")
else
    # remove known bad tags e.g. release-* in puppet-nssdb
    git tag -d $(git tag|grep ^release-)
    version="$(git describe --abbrev=0 --tags|sed 's/^[vV]//' || :)"
    # fallback to the version in metadata.json or Modulefile
    if [ -z "$version" ]; then
        if [ -r metadata.json ]; then
            version=$(python -c "import json; print json.loads(open('metadata.json').read(-1))['version']")
        elif [ -r Modulefile ]; then
            version=$(grep version Modulefile | sed "s@version *'\(.*\)'@\1@")
        fi
    fi
    # fallback to an arbitrary version
    if [ -z "$version" ]; then
        version=0.0.1
    fi
    setversionandrelease "$version" $(git log -n1 --format=format:%h)
    if [ -r metadata.json ]; then
        TARBALLS_OPS=$(egrep -c "^Source0.*tarballs.openstack.org" ${DISTGIT_DIR}/*spec||true)
        echo $TARBALLS_OPS
        git remote -v|head -1|awk '{print $2;}'|sed 's@.*/@@;s@\.git$@@'
        if [ $TARBALLS_OPS -ne 0 ]; then
            TARNAME=$(python -c "import json; print json.loads(open('metadata.json').read(-1))['name']")
        else
            TARNAME=$(git remote -v|head -1|awk '{print $2;}'|sed 's@.*/@@;s@\.git$@@')
        fi
    elif [ -r Modulefile ]; then
        TARNAME=$(git remote -v|head -1|awk '{print $2;}'|sed 's@.*/@@;s@\.git$@@')
    else
        TARNAME=${PROJECT_NAME}
    fi
    tar zcvf ../$VERSION.tar.gz --exclude=.git --transform="s@${PWD#/}@${TARNAME}-${VERSION}@" --show-transformed-names $PWD
    mkdir -p dist
    mv ../$VERSION.tar.gz dist/
fi

# https://bugs.launchpad.net/tripleo/+bug/1351491
if [[ "$PROJECT_NAME" =~  ^(diskimage-builder|tripleo-heat-templates|tripleo-image-elements)$ ]] ; then
    if [ "$VERSION" == "0.0.1" ] ; then
        VERSION=$(git tag | sort -V | tail -n 1)
    fi
fi

TARBALL=$(ls dist|grep '.tar.gz')

TARBALLREL=$(basename $TARBALL .tar.gz)-$RELEASE.tar.gz
mv dist/$TARBALL ${TOP_DIR}/SOURCES/$TARBALLREL

cd ${DISTGIT_DIR}
cp * ${TOP_DIR}/SOURCES/
cp *.spec ${TOP_DIR}/SPECS/
cd ${TOP_DIR}/SPECS/

sed -i -e "1i%define upstream_version $UPSTREAMVERSION\\" *.spec
sed -i -e "1i%global dlrn 1\\" *.spec
sed -i -e "s/UPSTREAMVERSION/$UPSTREAMVERSION/g" *.spec
VERSION=${VERSION/-/.}
sed -i -e "s/Version:.*/Version: $VERSION/g" *.spec
sed -i -e "s/Release:.*/Release: $RELEASE%{?dist}/g" *.spec
sed -i -e "s/Source0:.*/Source0: $TARBALLREL/g" *.spec
sed -i -e '/^%changelog.*/q' *.spec
cat *.spec
rpmbuild --define="_topdir ${TOP_DIR}" -bs ${TOP_DIR}/SPECS/*.spec

if [ "${ADDITIONAL_MOCK_OPTIONS}" != "" ]
then
    /usr/bin/mock ${MOCKOPTS} "${ADDITIONAL_MOCK_OPTIONS}" --postinstall --rebuild ${TOP_DIR}/SRPMS/*.src.rpm 2>&1 | tee $OUTPUT_DIRECTORY/mock.log
else
    /usr/bin/mock ${MOCKOPTS} --postinstall --rebuild ${TOP_DIR}/SRPMS/*.src.rpm 2>&1 | tee $OUTPUT_DIRECTORY/mock.log
fi

if [ $? -eq 0 ]
then
    if ! grep -F 'WARNING: Failed install built packages' $OUTPUT_DIRECTORY/mock.log; then
        touch $OUTPUT_DIRECTORY/installed
        exit 0
    else
        exit 1
    fi
else
    exit 1
fi
