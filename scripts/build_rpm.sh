#!/bin/bash -xe

source $(dirname $0)/common-functions

PROJECT_NAME=$1
OUTPUT_DIRECTORY=$2
USER_ID=$3 # chown resulting files to this UID
GROUP_ID=$4 # chown resulting files to this GUID

mkdir -p ~/rpmbuild/SOURCES ~/rpmbuild/SPECS $OUTPUT_DIRECTORY

trap finalize EXIT

# guess distro from /etc/redhat-release
read -d ' ' DISTRO < /etc/redhat-release

if [[ $DISTRO == Fedora ]]; then
    PBR_PACKAGES="https://kojipkgs.fedoraproject.org//packages/python-pbr/1.6.0/1.fc24/noarch/python-pbr-1.6.0-1.fc24.noarch.rpm \
https://kojipkgs.fedoraproject.org//packages/python-pbr/1.6.0/1.fc24/noarch/python3-pbr-1.6.0-1.fc24.noarch.rpm"
    DELOREAN_REPO="https://trunk.rdoproject.org/f21/current/delorean.repo"
elif [[ $DISTRO == CentOS ]]; then
     PBR_PACKAGES="http://cbs.centos.org/kojifiles/packages/python-pbr/1.6.0/1.el7/noarch/python-pbr-1.6.0-1.el7.noarch.rpm"
     DELOREAN_REPO="https://trunk.rdoproject.org/centos7/current/delorean.repo"
else
    echo  "ERROR : Couldn't guess DISTRO"
    exit 1
fi


# So that we don't have to maintain packaging for all dependencies we install RDO
# Which will contain a lot of the non openstack dependencies
if ! rpm -q rdo-release-kilo ; then
    yum install -y --nogpg https://rdo.fedorapeople.org/openstack-kilo/rdo-release-kilo.rpm
fi

# Install a recent version of python-pbr, needed to build some projects and only
# curently available in koji, remove this one we move onto the openstack-liberty repo above
if ! rpm -q python-pbr ; then
    yum install -y --nogpg $PBR_PACKAGES
fi

# install latest build tools updates from RDO repo
yum install -y --nogpg python-pip python-setuptools

# If in dev mode the user might not be building all of the packages, so we need
# to add the current upstream repository in order to have access to current dependencies
if [ "$DELOREAN_DEV" == "1" ] ; then
    curl $DELOREAN_REPO > /etc/yum.repos.d/public_current.repo
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
    # python-alembic version=0.8.2 but tarball is alembic-0.8.2.dev0
    if [[ "$TARBALL" =~ \.dev[0-9]+\. ]] ; then
        UPSTREAMVERSION=$(echo ${TARBALL} | sed 's/.*-\(.*\).tar.gz/\1/')
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
yum-builddep --disablerepo="*source" -y *.spec
rpmbuild -ba *.spec  --define="upstream_version $UPSTREAMVERSION"
find ~/rpmbuild/RPMS ~/rpmbuild/SRPMS -type f | xargs cp -t $OUTPUT_DIRECTORY

yum install -y --nogpg $(find $OUTPUT_DIRECTORY -type f -name "*rpm" | grep -v src.rpm) && touch $OUTPUT_DIRECTORY/installed || true
