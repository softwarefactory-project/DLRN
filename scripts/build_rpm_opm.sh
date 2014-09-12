#!/bin/bash -xe

mkdir -p ~/rpmbuild/SOURCES ~/rpmbuild/SPECS $2

cd /data/$1
for REPO in */.git ; do
    REPO=${REPO%%/*} # remove the /.git
    NAME=${REPO%%.git} # remove the .git, it may or may not be present
    SNAME=${NAME#*-} # remove the puppetlabs-
    tar --transform="s/$REPO/$NAME-master/" --exclude=.git -czf ${SNAME}-master.tar.gz $REPO
done

mv *.tar.gz ~/rpmbuild/SOURCES/

cd /data/$1_spec
cp * ~/rpmbuild/SOURCES/
cp *.spec ~/rpmbuild/SPECS/
cd ~/rpmbuild/SPECS/

# The puppet mudule package isn't based on any single repo so for now we hardcode
# VERSION and get RELEASE from $2 (contains commit ID of project that triggered the build)
UPSTREAMVERSION=2014.2
VERSION=2014.2
RELEASE=dev.${3##*/}

sed -i -e "s/Version:.*/Version: $VERSION/g" *.spec
sed -i -e "s/Release:.*/Release: $RELEASE%{?dist}/g" *.spec
cat *.spec
yum-builddep --disablerepo="*source" -y *.spec
rpmbuild -ba *.spec  --define="upstream_version $UPSTREAMVERSION"
find /rpmbuild/RPMS /rpmbuild/SRPMS -type f | xargs cp -t $2

yum install -y --nogpg $(find $2 -type f -name "*rpm" | grep -v src.rpm) && touch $2/installed || true
