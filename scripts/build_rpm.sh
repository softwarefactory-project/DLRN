#!/bin/bash -xe

set -o pipefail

source $(dirname $0)/common-functions

PROJECT_NAME=$1
OUTPUT_DIRECTORY=$2
DATA_DIR=$3

TOP_DIR=$(mktemp -d)

mkdir -p ${TOP_DIR}/SOURCES ${TOP_DIR}/SPECS $OUTPUT_DIRECTORY

trap finalize EXIT

cd ${DATA_DIR}/$PROJECT_NAME
git clean -dxf

for FILE in {test-,}requirements.txt
do
    if [ -f ${FILE} ]
    then
        sed -i "s/;python_version[!=<>]=\?.*//g" ${FILE}
        sed -i "s/;sys_platform[!=<>]=\?.*//g" ${FILE}
    fi
done

python setup.py sdist
TARBALL=$(ls dist)
# setup.py outputs warning (to stdout) in some cases (python-posix_ipc)
# so only look at the last line for version
UPSTREAMVERSION=$(python setup.py --version | tail -n 1)
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
    # try to follow Fedora guidelines for git snapshots (but include time too)
    # http://fedoraproject.org/wiki/Packaging:NamingGuidelines#Pre-Release_packages
    RELEASE=$(date -u +"0.99.%Y%m%d.%H%Mgit")
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
if [[ "$PROJECT_NAME" =~  ^(diskimage-builder|tripleo-heat-templates|tripleo-image-elements)$ ]] ; then
    if [ "$VERSION" == "0.0.1" ] ; then
        VERSION=$(git tag | sort -V | tail -n 1)
   fi
fi

mv dist/$TARBALL ${TOP_DIR}/SOURCES/

cd ${DATA_DIR}/${PROJECT_NAME}_distro
cp * ${TOP_DIR}/SOURCES/
cp *.spec ${TOP_DIR}/SPECS/
# Generate a diff of this distro repo when compared to Fedora Rawhide
if git fetch http://pkgs.fedoraproject.org/git/$PROJECT_NAME master ; then
    git diff HEAD..FETCH_HEAD > $OUTPUT_DIRECTORY/distro_delta.diff
fi
cd ${TOP_DIR}/SPECS/

cp  $(dirname $0)/centos.cfg $(dirname $0)/delorean.cfg.new

# Add the mostcurrent repo, we may have dependencies in it
if [ -e ${DATA_DIR}/repos/current/repodata ] ; then
    # delete the last line which must be """
    sed -i -e '$d' $(dirname $0)/delorean.cfg.new
    echo -e "\n[delorean]\nname=current\nbaseurl=file://${DATA_DIR}/repos/current\nenabled=1\ngpgcheck=0\npriority=1\n\"\"\"" >> $(dirname $0)/delorean.cfg.new
fi

# don't change delorean.cfg if the content hasn't changed to prevent
# mock from rebuilding its cache.
if [ ! -f $(dirname $0)/delorean.cfg ] || ! cmp $(dirname $0)/delorean.cfg $(dirname $0)/delorean.cfg.new; then
    cp $(dirname $0)/delorean.cfg.new $(dirname $0)/delorean.cfg
fi

sed -i -e "1i%define upstream_version $UPSTREAMVERSION\\" *.spec
sed -i -e "s/UPSTREAMVERSION/$UPSTREAMVERSION/g" *.spec
VERSION=${VERSION/-/.}
sed -i -e "s/Version:.*/Version: $VERSION/g" *.spec
sed -i -e "s/Release:.*/Release: $RELEASE%{?dist}/g" *.spec
sed -i -e "s/Source0:.*/Source0: $TARBALL/g" *.spec
cat *.spec
rpmbuild --define="_topdir ${TOP_DIR}" -bs ${TOP_DIR}/SPECS/*.spec
mock -v -r $(dirname $0)/delorean.cfg --postinstall --resultdir $OUTPUT_DIRECTORY --rebuild ${TOP_DIR}/SRPMS/*.src.rpm 2>&1 | tee $OUTPUT_DIRECTORY/mock.log

if ! grep -F 'WARNING: Failed install built packages' $OUTPUT_DIRECTORY/mock.log; then
    touch $OUTPUT_DIRECTORY/installed
fi
