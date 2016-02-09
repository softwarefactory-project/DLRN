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

cp  $(dirname $0)/${TARGET}.cfg ${DATA_DIR}/delorean.cfg.new

# Add the mostcurrent repo, we may have dependencies in it
if [ -e ${DATA_DIR}/repos/current/repodata ] ; then
    # delete the last line which must be """
    sed -i -e '$d' ${DATA_DIR}/delorean.cfg.new
    echo -e "\n[local]\nname=local\nbaseurl=file://${DATA_DIR}/repos/current\nenabled=1\ngpgcheck=0\npriority=1\n\"\"\"" >> ${DATA_DIR}/delorean.cfg.new
fi

# delete the last line which must be """
sed -i -e '$d' ${DATA_DIR}/delorean.cfg.new
curl ${BASEURL}/delorean-deps.repo >> ${DATA_DIR}/delorean.cfg.new
echo -e "\"\"\"" >> ${DATA_DIR}/delorean.cfg.new

if [ "$DELOREAN_DEV" = 1 ]; then
    # delete the last line which must be """
    sed -i -e '$d' ${DATA_DIR}/delorean.cfg.new
    curl ${BASEURL}/current/delorean.repo >> ${DATA_DIR}/delorean.cfg.new
    echo -e "\"\"\"" >> ${DATA_DIR}/delorean.cfg.new
fi

# don't change delorean.cfg if the content hasn't changed to prevent
# mock from rebuilding its cache.
if [ ! -f ${DATA_DIR}/delorean.cfg ] || ! cmp ${DATA_DIR}/delorean.cfg ${DATA_DIR}/delorean.cfg.new; then
    diff -u ${DATA_DIR}/delorean.cfg.new ${DATA_DIR}/delorean.cfg || :
    cp ${DATA_DIR}/delorean.cfg.new ${DATA_DIR}/delorean.cfg
fi

# if bootstraping Delorean, set the appropriate mock config option
if [ "DELOREAN_BOOTSTRAP" = 1 ]; then
    ADDITIONAL_MOCK_OPTIONS="-D 'delorean_bootstrap 1'"
fi

if [ "$1" != "openstack-puppet-modules" ] ; then
    $DIR/build_rpm.sh "$@"
else
    # Special case of the puppet modules as they don't
    # come from a single repo
    $DIR/build_rpm_opm.sh "$@"
fi
