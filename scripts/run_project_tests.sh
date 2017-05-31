#!/bin/bash
set -ex

# Simple script to test DLRN build from an upstream project
# Works either locally or in a zuul environment
GIT_BASE_URL="https://review.rdoproject.org/r/p"
OPENSTACK_GIT_URL="git://git.openstack.org"
RDOINFO="${1:-$GIT_BASE_URL/rdoinfo}"

# Display the current commit
git log -1

# Setup virtualenv with tox and use it
tox -epy27 --notest
. .tox/py27/bin/activate

# Default project to build
PROJECT_NAME="openstack/python-glanceclient"

# If we're actually building for a Zuul project, build that unless it's DLRN
[[ ! -z "${ZUUL_PROJECT}" && "${ZUUL_PROJECT}" != "DLRN" ]] && PROJECT_NAME="${ZUUL_PROJECT}"

PROJECT_TO_BUILD=${PROJECT_NAME#*/}

# Fetch rdoinfo using zuul_cloner, if available
if [ -e /usr/bin/zuul-cloner ] ; then
    zuul-cloner --workspace /tmp ${GIT_BASE_URL} rdoinfo
else
    rm -rf /tmp/rdoinfo
    git clone ${RDOINFO} /tmp/rdoinfo
fi

# Map to rdoinfo
PROJECT_TO_BUILD_MAPPED=$(rdopkg findpkg $PROJECT_TO_BUILD -l /tmp/rdoinfo | awk '/^name:/ {print $2}')
PROJECT_IN_RDOINFO=$(rdopkg findpkg $PROJECT_TO_BUILD -l /tmp/rdoinfo | awk '/^project:/ {print $2}')
if [[ "$PROJECT_IN_RDOINFO" =~ puppet- ]]; then
    PROJECT_DISTRO="puppet/$PROJECT_IN_RDOINFO-distgit"
else
    PROJECT_DISTRO="openstack/$PROJECT_IN_RDOINFO-distgit"
fi
PROJECT_DISTRO_DIR=${PROJECT_TO_BUILD_MAPPED}_distro
PROJECT_DISTRO_BRANCH="rpm-master"

# Prepare config
target="centos"
baseurl="http://trunk.rdoproject.org/centos7/"
src="master"
branch=""

if [[ "${ZUUL_BRANCH}" =~ stable/ ]]; then
    branch=$(sed "s#stable/##" <<< "${ZUUL_BRANCH}")
    baseurl="http://trunk.rdoproject.org/${branch}/centos7/"
    src=${ZUUL_BRANCH}
fi

# Update the configuration
sed -i "s%target=.*%target=${target}%" projects.ini
sed -i "s%source=.*%source=${src}%" projects.ini
sed -i "s%baseurl=.*%baseurl=${baseurl}%" projects.ini
sed -i "s%^tags=.*%tags=${branch}%" projects.ini

# Prepare directories
mkdir -p data/repos
if [ -e /usr/bin/zuul-cloner ]; then
    zuul-cloner --workspace data/ $GIT_BASE_URL $PROJECT_DISTRO --branch $PROJECT_DISTRO_BRANCH
    mv data/$PROJECT_DISTRO data/$PROJECT_DISTRO_DIR
    # same for source git
    zuul-cloner --workspace data/ --zuul-ref $ZUUL_REF --zuul-branch $ZUUL_BRANCH --zuul-url $ZUUL_URL  $OPENSTACK_GIT_URL ${PROJECT_NAME}
    mv data/${PROJECT_NAME} data/${PROJECT_TO_BUILD_MAPPED}
else
    # We're outside the gate, just do a regular git clone
    pushd data/
    # rm -rf first for idempotency
    rm -rf $PROJECT_DISTRO_DIR
    git clone "${GIT_BASE_URL}/${PROJECT_DISTRO}" $PROJECT_DISTRO_DIR
    cd $PROJECT_DISTRO_DIR
    git checkout $PROJECT_DISTRO_BRANCH
    # same for source git
    cd ..
    rm -rf $PROJECT_TO_BUILD_MAPPED
    git clone "${OPENSTACK_GIT_URL}/${PROJECT_NAME}" ${PROJECT_TO_BUILD_MAPPED}
    cd ${PROJECT_TO_BUILD_MAPPED}
    popd
fi


# If the commands below throws an error we still want the logs
function copy_logs() {
    mkdir -p logs
    rsync -avzr data/repos logs/centos
    rsync -avzrL data/repos/current logs/centos
}
trap copy_logs ERR EXIT

# Run DLRN
dlrn --head-only --package-name $PROJECT_TO_BUILD_MAPPED --use-public --local --info-repo /tmp/rdoinfo --verbose-mock
copy_logs
# Clean up mock cache, just in case there is a change for the next run
mock -r data/dlrn-1.cfg --scrub=all
