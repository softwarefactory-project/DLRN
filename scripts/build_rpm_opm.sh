#!/bin/bash -xe

set -o pipefail

source $(dirname $0)/common-functions

# check if spec has multiple Source fields
sources_spec=$(grep ^Source ${DATA_DIR}/${PROJECT_NAME}_distro/*.spec|wc -l)
sources_upstream=$(ls -d ${DATA_DIR}/${PROJECT_NAME}/|wc -l)

setversionandrelease $(git describe --tags)
for REPO in $(ls -d */); do
    NAME=${REPO%%/} # remove the /
    if [ $sources_upstream -le 1 ]; then
        # Special case for github.com/redhat-openstack/openstack-puppet-modules
        # as the only source repo listed as "upstream" in rdoinfo
        tar --transform="s#^#openstack-puppet-modules/#" --exclude=.git -czf openstack-puppet-modules.tar.gz *
        break
    fi
    NAME=$(echo $NAME | sed -r 's/_/-/') # Some puppet modules names are not compliant (Ex: puppet_aviator)
    SNAME=${NAME#*-} # remove the puppetlabs-
    if [ $sources_spec = 1 ]; then
        # new OPM spec: combine all modules into one tarball
        tar --append --transform="s#$REPO#openstack-puppet-modules/$SNAME#" --exclude=.git -f openstack-puppet-modules.tar $REPO
        # fake Puppetfile for new OPM spec
        printf "mod '$SNAME'\n\n" >> Puppetfile
    else
        # old OPM spec with separate Source for each puppet module
        tar --transform="s/$REPO/$NAME-master/" --exclude=.git -czf ${SNAME}-master.tar.gz $REPO
    fi
done

if [ -f openstack-puppet-modules.tar ]; then
    tar --append --transform="s#Puppetfile#openstack-puppet-modules/Puppetfile#" -f openstack-puppet-modules.tar Puppetfile
    gzip openstack-puppet-modules.tar
fi
mv *.tar.gz ${TOP_DIR}/SOURCES/

cd ${DATA_DIR}/${PROJECT_NAME}_distro
cp * ${TOP_DIR}/SOURCES/
cp *.spec ${TOP_DIR}/SPECS/
cd ${TOP_DIR}/SPECS/

sed -i -e "1i%define upstream_version $UPSTREAMVERSION\\" *.spec
sed -i -e "s/Version:.*/Version: $VERSION/g" *.spec
sed -i -e "s/Release:.*/Release: $RELEASE%{?dist}/g" *.spec
cat *.spec
rpmbuild --define="_topdir ${TOP_DIR}" -bs *.spec
/usr/bin/mock -v -r ${DATA_DIR}/delorean.cfg --postinstall --resultdir $OUTPUT_DIRECTORY --rebuild ${TOP_DIR}/SRPMS/*.src.rpm 2>&1 | tee $OUTPUT_DIRECTORY/mock.log

if ! grep -F 'WARNING: Failed install built packages' $OUTPUT_DIRECTORY/mock.log; then
    touch $OUTPUT_DIRECTORY/installed
fi
