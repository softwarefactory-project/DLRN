#!/bin/bash -xe

PROJECT_NAME=$1
OUTPUT_DIRECTORY=$2
USER_ID=$3 # chown resulting files to this UID
GROUP_ID=$4 # chown resulting files to this GUID

mkdir -p ~/rpmbuild/SOURCES ~/rpmbuild/SPECS $OUTPUT_DIRECTORY

cd /data/$PROJECT_NAME
for REPO in */.git ; do
    REPO=${REPO%%/*} # remove the /.git
    NAME=${REPO%%.git} # remove the .git, it may or may not be present
    SNAME=${NAME#*-} # remove the puppetlabs-
    tar --transform="s/$REPO/$NAME-master/" --exclude=.git -czf ${SNAME}-master.tar.gz $REPO
done

mv *.tar.gz ~/rpmbuild/SOURCES/

cd /data/${PROJECT_NAME}_spec
cp * ~/rpmbuild/SOURCES/
cp *.spec ~/rpmbuild/SPECS/
cd ~/rpmbuild/SPECS/

# The puppet module package isn't based on any single repo so for now we hardcode
# VERSION and get RELEASE from $OUTPUT_DIRECTORY (contains commit ID of project that triggered the build)
UPSTREAMVERSION=2014.2
VERSION=2014.2
RELEASE=dev.${2##*/}

sed -i -e "s/Version:.*/Version: $VERSION/g" *.spec
sed -i -e "s/Release:.*/Release: $RELEASE%{?dist}/g" *.spec
cat *.spec
yum-builddep --disablerepo="*source" -y *.spec
rpmbuild -ba *.spec  --define="upstream_version $UPSTREAMVERSION"
find ~/rpmbuild/RPMS ~/rpmbuild/SRPMS -type f | xargs cp -t $OUTPUT_DIRECTORY

yum install -y --nogpg $(find $OUTPUT_DIRECTORY -type f -name "*rpm" | grep -v src.rpm) && touch $OUTPUT_DIRECTORY/installed || true

chown -R $USER_ID:$GROUP_ID $OUTPUT_DIRECTORY
