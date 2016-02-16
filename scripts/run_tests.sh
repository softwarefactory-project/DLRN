#!/usr/bin/bash
set -eux

# Simple CI test to sanity test commits

# Display the current commit
git log -1

set +u
if [ -z "$GERRIT_PROJECT" -o "$GERRIT_PROJECT" = "openstack-packages/delorean" ] ; then
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
set -u

# test that the mock command is present
type -p mock

# Build this if not building a specific project
PROJECT_TO_BUILD=python-glanceclient
PROJECT_TO_BUILD_MAPPED=$(./scripts/map-project-name $PROJECT_TO_BUILD)

# If this is a CI run for one of the distro repositories then we pre download it
# into the data directory, delorean wont change it because we are using --dev
[ -z "${GERRIT_PROJECT-}" ] && GERRIT_PROJECT=""
[ -z "${ZUUL_PROJECT-}" ] && ZUUL_PROJECT=""
if [ -n "$GERRIT_PROJECT" ] && [ "$GERRIT_PROJECT" != "openstack-packages/delorean" ] ; then
    mkdir -p data/repos
    PROJECT_TO_BUILD=${GERRIT_PROJECT#*/}
    PROJECT_TO_BUILD_MAPPED=$(./scripts/map-project-name $PROJECT_TO_BUILD)
    PROJECT_DISTRO_DIR=${PROJECT_TO_BUILD_MAPPED}_distro
    # Use different cloning directory for regular and packaging repositories
    if [ "${GERRIT_PROJECT/openstack-packages\/*/packages}" == "packages" ] ; then
        PROJECT_CLONE_DIR=$PROJECT_DISTRO_DIR
    else
        PROJECT_CLONE_DIR=$PROJECT_TO_BUILD_MAPPED
    fi
    git clone https://$GERRIT_HOST/"$GERRIT_PROJECT" data/$PROJECT_CLONE_DIR
    pushd data/$PROJECT_CLONE_DIR
    git fetch https://$GERRIT_HOST/$GERRIT_PROJECT $GERRIT_REFSPEC && git checkout FETCH_HEAD
    popd
# If this a CI run triggered by Zuul. Use zuul-cloner to fetch the project at the right
# revision.
elif [ -n "$ZUUL_PROJECT" ] ; then
    # test that the zuul-cloner command is present
    type -p zuul-cloner
    mkdir -p data/repos
    PROJECT_TO_BUILD=${ZUUL_PROJECT%-distgit}
    PROJECT_TO_BUILD_MAPPED=$(./scripts/map-project-name $PROJECT_TO_BUILD)
    PROJECT_DISTRO_DIR=${PROJECT_TO_BUILD_MAPPED}_distro
    zuul-cloner --workspace data/ $GERRIT_CLONE_URL $ZUUL_PROJECT
    mv data/$ZUUL_PROJECT data/$PROJECT_DISTRO_DIR
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

function run_delorean() {
    export DISTRO="${1}"
    update_config $DISTRO
    # Run delorean
    delorean --config-file projects.ini --head-only --package-name $PROJECT_TO_BUILD_MAPPED --dev
    copy_logs
}

# If the commands below throws an error we still want the logs
trap copy_logs ERR EXIT

run_delorean centos
