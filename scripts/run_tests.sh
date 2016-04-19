#!/bin/bash
set -ex

# Simple script to test that delorean works either locally or in a zuul environment
RDOINFO="${1}"
GIT_BASE_URL="https://review.rdoproject.org/r/p"

# Display the current commit
git log -1

# Run bash unit tests
./scripts/run_sh_tests.sh

# Setup virtualenv with tox and use it
tox -epy27 --notest
. .tox/py27/bin/activate

# Test that the mock command is present
type -p mock

# Default project to build
PROJECT_DISTRO="openstack/glanceclient-distgit"

# If we're actually building for a Zuul project, build that unless it's DLRN
[[ ! -z "${ZUUL_PROJECT}" && "${ZUUL_PROJECT}" != "DLRN" ]] && PROJECT_DISTRO="${ZUUL_PROJECT}"

# The rdoinfo project name isn't prefixed by openstack/ or suffixed by -distgit
PROJECT_TO_BUILD=${PROJECT_DISTRO#*/}
PROJECT_TO_BUILD=$(echo ${PROJECT_TO_BUILD} |sed -e "s/-distgit//")

# Map to rdoinfo
PROJECT_TO_BUILD_MAPPED=$(./scripts/map-project-name $PROJECT_TO_BUILD $RDOINFO)
PROJECT_DISTRO_DIR=${PROJECT_TO_BUILD_MAPPED}_distro

# Prepare directories
mkdir -p data/repos
if [[ ! -z "${ZUUL_PROJECT}" ]]; then
    # Ensure zuul-cloner is present
    type -p zuul-cloner
    zuul-cloner --workspace data/ $GIT_BASE_URL $PROJECT_DISTRO
    mv data/$PROJECT_DISTRO data/$PROJECT_DISTRO_DIR
fi

function update_config() {
    # Ensures configuration is set properly according to distribution and branch
    case "${1}" in
        centos)
          target="centos"
          baseurl="http://trunk.rdoproject.org/centos7/"
          src="master"
          branch=""
          ;;
        fedora)
          target="fedora"
          baseurl="https://trunk.rdoproject.org/f23"
          src="master"
          branch=""
          ;;
        *)
          target="centos"
          baseurl="http://trunk.rdoproject.org/centos7/"
          src="master"
          branch=""
          ;;
    esac

    # If this is a commit on a specific branch, make sure we're using it
    [ -n "${ZUUL_BRANCH-}" ] && TARGET_BRANCH=$ZUUL_BRANCH
    if [[ "${target}" == "centos" \
          && "${TARGET_BRANCH}" =~ rpm- \
          && "${TARGET_BRANCH}" != "rpm-master" ]]; then
      branch=$(sed "s/rpm-//" <<< "${TARGET_BRANCH}")
      baseurl="http://trunk.rdoproject.org/${branch}/centos7/"
      src="stable/${branch}"
    fi

    # Update the configration
    sed -i "s%target=.*%target=${DISTRO}%" projects.ini
    sed -i "s%source=.*%source=${src}%" projects.ini
    sed -i "s%baseurl=.*%baseurl=${baseurl}%" projects.ini
    sed -i "s%tags=.*%tags=${branch}%" projects.ini
}

function copy_logs() {
    mkdir -p logs
    rsync -avzr data/repos logs/$DISTRO
}

function run_dlrn() {
    export DISTRO="${1}"
    update_config $DISTRO
    # Run delorean
    delorean --config-file projects.ini --head-only --package-name $PROJECT_TO_BUILD_MAPPED --dev
    copy_logs
    # Clean up mock cache, just in case there is a change for the next run
    mock -r data/dlrn.cfg --scrub=all
}

# If the commands below throws an error we still want the logs
trap copy_logs ERR EXIT

run_dlrn centos
