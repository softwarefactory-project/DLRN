#!/bin/bash -xe

source $(dirname $0)/common-functions

PROJECT_NAME=$1
OUTPUT_DIRECTORY=$2
USER_ID=$3 # chown resulting files to this UID
GROUP_ID=$4 # chown resulting files to this GUID

mkdir -p ~/rpmbuild/SOURCES ~/rpmbuild/SPECS $OUTPUT_DIRECTORY

trap finalize EXIT

# So that we don't have to maintain packaging for all dependencies we install RDO
# Which will contain a lot of the non openstack dependencies
if ! rpm -q rdo-release-kilo ; then
    yum install -y --nogpg https://rdo.fedorapeople.org/openstack-kilo/rdo-release-kilo.rpm
fi

# Install a recent version of python-pbr, needed to build some projects and only
# curently available in koji, remove this one we move onto the openstack-liberty repo above
if ! rpm -q python-pbr ; then
    yum install -y --nogpg https://kojipkgs.fedoraproject.org//packages/python-pbr/1.3.0/1.fc24/noarch/python-pbr-1.3.0-1.fc24.noarch.rpm
fi

# install latest build tools updates from RDO repo
yum install -y --nogpg python-pip python-setuptools

# If in dev mode the user might not be building all of the packages, so we need
# to add the current upstream repository in order to have access to current dependencies
if [ "$DELOREAN_DEV" == "1" ] ; then
    curl http://trunk.rdoproject.org/f21/current/delorean.repo > /etc/yum.repos.d/public_current.repo
fi

cd /data/$PROJECT_NAME
rm -f dist/*

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
setversionandrelease $(python setup.py --version | tail -n 1)

# https://bugs.launchpad.net/tripleo/+bug/1351491
if [[ "$PROJECT_NAME" =~  ^(diskimage-builder|tripleo-heat-templates|tripleo-image-elements)$ ]] ; then
    if [ "$VERSION" == "0.0.1" ] ; then
        VERSION=$(git tag | sort -V | tail -n 1)
   fi
fi

mv dist/$TARBALL ~/rpmbuild/SOURCES/

cd /data/${PROJECT_NAME}_distro
cp * ~/rpmbuild/SOURCES/
cp *.spec ~/rpmbuild/SPECS/
# Generate a diff of this distro repo when compared to Fedora Rawhide
if git fetch http://pkgs.fedoraproject.org/git/$PROJECT_NAME master ; then
    git diff HEAD..FETCH_HEAD > $OUTPUT_DIRECTORY/distro_delta.diff
fi
cd ~/rpmbuild/SPECS/

# Add the mostcurrent repo, we may have dependencies in it
if [ -e /data/repos/current/repodata ] ; then
    echo -e '[current]\nname=current\nbaseurl=file:///data/repos/current\nenabled=1\ngpgcheck=0\npriority=1' > /etc/yum.repos.d/current.repo
fi

sed -i -e "s/UPSTREAMVERSION/$UPSTREAMVERSION/g" *.spec
VERSION=${VERSION/-/.}
sed -i -e "s/Version:.*/Version: $VERSION/g" *.spec
sed -i -e "s/Release:.*/Release: $RELEASE%{?dist}/g" *.spec
sed -i -e "s/Source0:.*/Source0: $TARBALL/g" *.spec
cat *.spec
yum-builddep -y *.spec
rpmbuild -ba *.spec  --define="upstream_version $UPSTREAMVERSION"
find ~/rpmbuild/RPMS ~/rpmbuild/SRPMS -type f | xargs cp -t $OUTPUT_DIRECTORY

yum install -y --nogpg $(find $OUTPUT_DIRECTORY -type f -name "*rpm" | grep -v src.rpm) && touch $OUTPUT_DIRECTORY/installed || true
