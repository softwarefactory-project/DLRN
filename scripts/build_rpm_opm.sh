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
    NAME=`echo $NAME | sed -r 's/_/-/'` # Some puppet modules names are not compliant (Ex: puppet_aviator)
    SNAME=${NAME#*-} # remove the puppetlabs-
    tar --transform="s/$REPO/$NAME-master/" --exclude=.git -czf ${SNAME}-master.tar.gz $REPO
done

mv *.tar.gz ~/rpmbuild/SOURCES/

cd /data/${PROJECT_NAME}_distro
cp * ~/rpmbuild/SOURCES/
cp *.spec ~/rpmbuild/SPECS/
# Generate a diff of this distro repo when compared to Fedora Rawhide
if git fetch http://pkgs.fedoraproject.org/git/$PROJECT_NAME master ; then
    git diff HEAD..FETCH_HEAD > $OUTPUT_DIRECTORY/distro_delta.diff
fi
cd ~/rpmbuild/SPECS/

# The puppet module package isn't based on any single repo so for now we hardcode
# VERSION and get RELEASE from $OUTPUT_DIRECTORY (contains commit ID of project that triggered the build)
UPSTREAMVERSION=2015.1
VERSION=2015.1
RELEASE=dev.${2##*/}

sed -i -e "s/Version:.*/Version: $VERSION/g" *.spec
sed -i -e "s/Release:.*/Release: $RELEASE%{?dist}/g" *.spec
cat *.spec
yum-builddep --disablerepo="*source" -y *.spec
rpmbuild -ba *.spec  --define="upstream_version $UPSTREAMVERSION"
find ~/rpmbuild/RPMS ~/rpmbuild/SRPMS -type f | xargs cp -t $OUTPUT_DIRECTORY

yum install -y --nogpg $(find $OUTPUT_DIRECTORY -type f -name "*rpm" | grep -v src.rpm) && touch $OUTPUT_DIRECTORY/installed || true

chown -R $USER_ID:$GROUP_ID $OUTPUT_DIRECTORY
