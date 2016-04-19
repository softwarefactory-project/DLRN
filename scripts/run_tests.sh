#!/bin/bash
set -ex

# Simple CI test to sanity test commits within a gerrit/zuul ecosystem
RDOINFO="${1}"
GIT_BASE_URL="https://review.rdoproject.org/r/p"

# Display the current commit
git log -1

set +u
if [ -z "${GERRIT_PROJECT}" -a -z "${ZUUL_PROJECT}" -o "${ZUUL_PROJECT}" = "DLRN" ]; then
    # Run unit tests
    tox -epy27

    # Run pep8 tests
    tox -epep8

    # Run bash unit tests
    ./scripts/run_sh_tests.sh
else
    # Only prepare virtualenv
    tox -epy27 --notest
fi

# Use the env setup by tox
. .tox/py27/bin/activate

# test that the mock command is present
type -p mock

# If we're building for a gerrit or zuul project, build that unless it's DLRN
[[ ! -z "${GERRIT_PROJECT}" && "${GERRIT_PROJECT}" != "DLRN" ]] && PROJECT="${GERRIT_PROJECT}"
[[ ! -z "${ZUUL_PROJECT}" && "${ZUUL_PROJECT}" != "DLRN" ]] && PROJECT="${ZUUL_PROJECT%-distgit}"

# Set project to build and parameters, defaults to python-glanceclient
[[ -z "${PROJECT}" ]] && PROJECT="openstack/glanceclient"
PROJECT_TO_BUILD=${PROJECT}
PROJECT_TO_BUILD=${PROJECT_TO_BUILD#*/}
PROJECT_TO_BUILD_MAPPED=$(./scripts/map-project-name $PROJECT_TO_BUILD $RDOINFO)
PROJECT_DISTRO_DIR=${PROJECT_TO_BUILD_MAPPED}_distro

mkdir -p data/repos
# Prepare directories if it's a gerrit project
if [[ ! -z "${GERRIT_PROJECT}" ]]; then
    # Use different cloning directory for regular and packaging repositories
    if [ "${GERRIT_PROJECT/openstack-packages\/*/packages}" == "packages" ]; then
        PROJECT_CLONE_DIR=$PROJECT_DISTRO_DIR
    else
        PROJECT_CLONE_DIR=$PROJECT_TO_BUILD_MAPPED
    fi

    git clone "${GIT_BASE_URL}/${GERRIT_PROJECT}" data/$PROJECT_CLONE_DIR
    pushd data/$PROJECT_CLONE_DIR
    git fetch "${GIT_BASE_URL}/${GERRIT_PROJECT}" $GERRIT_REFSPEC && git checkout FETCH_HEAD
    popd
fi

# Prepare directories if it's a zuul project
if [[ ! -z "${ZUUL_PROJECT}" ]]; then
    # Ensure zuul-cloner is present
    type -p zuul-cloner
    zuul-cloner --workspace data/ $GIT_BASE_URL $PROJECT
    mv data/$PROJECT_TO_BUILD data/$PROJECT_DISTRO_DIR
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
    [ -n "${GERRIT_BRANCH-}" ] && TARGET_BRANCH=$GERRIT_BRANCH
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
