#!/bin/bash
set -ex

# Simple script to test that DLRN works either locally or in a zuul environment
GIT_BASE_URL="https://review.rdoproject.org/r/p"
RDOINFO="${1:-$GIT_BASE_URL/rdoinfo}"

# Display the current commit
git log -1

# Run bash unit tests
./scripts/run_sh_tests.sh

# Setup virtualenv with tox and use it
tox -epy27 --notest
. .tox/py27/bin/activate

# Default project to build
PROJECT_DISTRO="openstack/glanceclient-distgit"
PROJECT_DISTRO_BRANCH="rpm-master"

# If we're actually building for a Zuul project, build that unless it's DLRN
[[ ! -z "${ZUUL_PROJECT}" && "${ZUUL_PROJECT}" != "DLRN" ]] && PROJECT_DISTRO="${ZUUL_PROJECT}"

# The rdoinfo project name isn't prefixed by openstack/ or suffixed by -distgit
PROJECT_TO_BUILD=${PROJECT_DISTRO#*/}
PROJECT_TO_BUILD=$(sed "s/-distgit//" <<< "${PROJECT_TO_BUILD}")

# Map to rdoinfo
PROJECT_TO_BUILD_MAPPED=$(./scripts/map-project-name $PROJECT_TO_BUILD $RDOINFO)
PROJECT_DISTRO_DIR=${PROJECT_TO_BUILD_MAPPED}_distro

# Prepare config
target="centos"
baseurl="http://trunk.rdoproject.org/centos7/"
src="master"
branch=""

# If we're testing a commit on a specific branch, make sure we're using it
if [[ "${ZUUL_BRANCH}" =~ rpm- && "${ZUUL_BRANCH}" != "rpm-master" ]]; then
    branch=$(sed "s/rpm-//" <<< "${ZUUL_BRANCH}")
    baseurl="http://trunk.rdoproject.org/${branch}/centos7/"
    src="stable/${branch}"
    PROJECT_DISTRO_BRANCH=$ZUUL_BRANCH
fi

# Update the configuration
sed -i "s%target=.*%target=${target}%" projects.ini
sed -i "s%source=.*%source=${src}%" projects.ini
sed -i "s%baseurl=.*%baseurl=${baseurl}%" projects.ini
sed -i "s%tags=.*%tags=${branch}%" projects.ini

# Prepare directories
mkdir -p data/repos
if [ -e /usr/bin/zuul-cloner ]; then
    zuul-cloner --workspace data/ $GIT_BASE_URL $PROJECT_DISTRO --branch $PROJECT_DISTRO_BRANCH
    mv data/$PROJECT_DISTRO data/$PROJECT_DISTRO_DIR
else
    # We're outside the gate, just do a regular git clone
    pushd data/
    # rm -rf first for idempotency
    rm -rf $PROJECT_DISTRO_DIR
    git clone "${GIT_BASE_URL}/${PROJECT_DISTRO}" $PROJECT_DISTRO_DIR
    cd $PROJECT_DISTRO_DIR
    git checkout $PROJECT_DISTRO_BRANCH
    popd
fi

# If the commands below throws an error we still want the logs
function copy_logs() {
    mkdir -p logs
    rsync -avzr data/repos logs/centos
}
trap copy_logs ERR EXIT

# Run DLRN
dlrn --config-file projects.ini --head-only --package-name $PROJECT_TO_BUILD_MAPPED --dev
copy_logs
# Clean up mock cache, just in case there is a change for the next run
mock -r data/dlrn-1.cfg --scrub=all
