#!/bin/bash -e

DIR=$(realpath $(dirname $0))

TARGET=$1
shift
PROJECT_NAME=$1
OUTPUT_DIRECTORY=$2
DATA_DIR=$3

exec > ${OUTPUT_DIRECTORY}/rpmbuild.log 2>&1

set -x

cp  $(dirname $0)/${TARGET}.cfg $(dirname $0)/delorean.cfg.new

# Add the mostcurrent repo, we may have dependencies in it
if [ -e ${DATA_DIR}/repos/current/repodata ] ; then
    # delete the last line which must be """
    sed -i -e '$d' $(dirname $0)/delorean.cfg.new
    echo -e "\n[local]\nname=local\nbaseurl=file://${DATA_DIR}/repos/current\nenabled=1\ngpgcheck=0\npriority=1\n\"\"\"" >> $(dirname $0)/delorean.cfg.new
fi

if [ "$DELOREAN_DEV" = 1 ]; then
    # delete the last line which must be """
    sed -i -e '$d' $(dirname $0)/delorean.cfg.new
    curl http://trunk.rdoproject.org/f21/current/delorean.repo >> $(dirname $0)/delorean.cfg.new
    echo -e "\"\"\"" >> $(dirname $0)/delorean.cfg.new
fi

# don't change delorean.cfg if the content hasn't changed to prevent
# mock from rebuilding its cache.
if [ ! -f $(dirname $0)/delorean.cfg ] || ! cmp $(dirname $0)/delorean.cfg $(dirname $0)/delorean.cfg.new; then
    diff -u $(dirname $0)/delorean.cfg.new $(dirname $0)/delorean.cfg || :
    cp $(dirname $0)/delorean.cfg.new $(dirname $0)/delorean.cfg
fi

if [ "$1" != "openstack-puppet-modules" ] ; then
    $DIR/build_rpm.sh "$@"
else
    # Special case of the puppet modules as they don't
    # come from a single repo
    $DIR/build_rpm_opm.sh "$@"
fi
