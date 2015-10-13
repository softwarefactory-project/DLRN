#!/bin/bash -xe

set -o pipefail

source $(dirname $0)/common-functions

# check if spec has multiple Source fields
sources_spec=$(grep ^Source ${DATA_DIR}/${PROJECT_NAME}_distro/*.spec|wc -l)
sources_upstream=$(ls -d ${DATA_DIR}/${PROJECT_NAME}/|wc -l)

for REPO in $(ls -d */); do
    NAME=${REPO%%/} # remove the /
    if [ $sources_upstream -le 1 ]; then
        # Special case for github.com/redhat-openstack/openstack-puppet-modules
        # as the only source repo listed as "upstream" in rdoinfo
        tar --transform="s#^#openstack-puppet-modules-master-patches/#" --exclude=.git -czf openstack-puppet-modules-master-patches.tar.gz *
        break
    fi
    NAME=$(echo $NAME | sed -r 's/_/-/') # Some puppet modules names are not compliant (Ex: puppet_aviator)
    SNAME=${NAME#*-} # remove the puppetlabs-
    if [ $sources_spec = 1 ]; then
        # new OPM spec: combine all modules into one tarball
        tar --append --transform="s#$REPO#openstack-puppet-modules-master-patches/$SNAME#" --exclude=.git -f openstack-puppet-modules-master-patches.tar $REPO
        # fake Puppetfile for new OPM spec
        printf "mod '$SNAME'\n\n" >> Puppetfile
    else
        # old OPM spec with separate Source for each puppet module
        tar --transform="s/$REPO/$NAME-master/" --exclude=.git -czf ${SNAME}-master.tar.gz $REPO
    fi
done

if [ -f openstack-puppet-modules-master-patches.tar ]; then
    tar --append --transform="s#Puppetfile#openstack-puppet-modules-master-patches/Puppetfile#" -f openstack-puppet-modules-master-patches.tar Puppetfile
    gzip openstack-puppet-modules-master-patches.tar
fi
mv *.tar.gz ${TOP_DIR}/SOURCES/

cd ${DATA_DIR}/${PROJECT_NAME}_distro
cp * ${TOP_DIR}/SOURCES/
cp *.spec ${TOP_DIR}/SPECS/
# Generate a diff of this distro repo when compared to Fedora Rawhide
if git fetch http://pkgs.fedoraproject.org/git/$PROJECT_NAME master; then
    git diff HEAD..FETCH_HEAD > $OUTPUT_DIRECTORY/distro_delta.diff
fi
cd ${TOP_DIR}/SPECS/

# The puppet module package isn't based on any single repo so for now
# we hardcode VERSION and get RELEASE from $OUTPUT_DIRECTORY (contains
# commit ID of project that triggered the build)
UPSTREAMVERSION=7.0.0
VERSION=$UPSTREAMVERSION
RELEASE=dev.${2##*/}

sed -i -e "1i%define upstream_version $UPSTREAMVERSION\\" *.spec
sed -i -e "s/Version:.*/Version: $VERSION/g" *.spec
sed -i -e "s/Release:.*/Release: $RELEASE%{?dist}/g" *.spec
cat *.spec
rpmbuild --define="_topdir ${TOP_DIR}" -bs *.spec
/usr/bin/mock -v -r $(dirname $0)/delorean.cfg --postinstall --resultdir $OUTPUT_DIRECTORY --rebuild ${TOP_DIR}/SRPMS/*.src.rpm 2>&1 | tee $OUTPUT_DIRECTORY/mock.log

if ! grep -F 'WARNING: Failed install built packages' $OUTPUT_DIRECTORY/mock.log; then
    touch $OUTPUT_DIRECTORY/installed
fi
