#!/bin/bash -e

DIR=$(realpath $(dirname $0))

TARGET=$1
shift
PROJECT_NAME=$1
OUTPUT_DIRECTORY=$2
DATA_DIR=$3
BASEURL=$4

exec > ${OUTPUT_DIRECTORY}/rpmbuild.log 2>&1

set -x

cp  $(dirname $0)/${TARGET}.cfg ${DATA_DIR}/dlrn.cfg.new

# Add the mostcurrent repo, we may have dependencies in it
if [ -e ${DATA_DIR}/repos/current/repodata ] ; then
    # delete the last line which must be """
    sed -i -e '$d' ${DATA_DIR}/dlrn.cfg.new
    echo -e "\n[local]\nname=local\nbaseurl=file://${DATA_DIR}/repos/current\nenabled=1\ngpgcheck=0\npriority=1\n\"\"\"" >> ${DATA_DIR}/dlrn.cfg.new
fi

# delete the last line which must be """
sed -i -e '$d' ${DATA_DIR}/dlrn.cfg.new
curl ${BASEURL}/delorean-deps.repo >> ${DATA_DIR}/dlrn.cfg.new
echo -e "\"\"\"" >> ${DATA_DIR}/dlrn.cfg.new

if [ "$DELOREAN_DEV" = 1 ]; then
    # delete the last line which must be """
    sed -i -e '$d' ${DATA_DIR}/dlrn.cfg.new
    curl ${BASEURL}/current/delorean.repo >> ${DATA_DIR}/dlrn.cfg.new
    echo -e "\"\"\"" >> ${DATA_DIR}/dlrn.cfg.new
fi

# don't change dlrn.cfg if the content hasn't changed to prevent
# mock from rebuilding its cache.
if [ ! -f ${DATA_DIR}/dlrn.cfg ] || ! cmp ${DATA_DIR}/dlrn.cfg ${DATA_DIR}/dlrn.cfg.new; then
    diff -u ${DATA_DIR}/dlrn.cfg.new ${DATA_DIR}/dlrn.cfg || :
    cp ${DATA_DIR}/dlrn.cfg.new ${DATA_DIR}/dlrn.cfg
fi

# if bootstraping, set the appropriate mock config option
if [ "REPO_BOOTSTRAP" = 1 ]; then
    ADDITIONAL_MOCK_OPTIONS="-D 'repo_bootstrap 1'"
fi

if [ "$1" != "openstack-puppet-modules" ] ; then
    $DIR/build_rpm.sh "$@"
else
    # Special case of the puppet modules as they don't
    # come from a single repo
    $DIR/build_rpm_opm.sh "$@"
fi
