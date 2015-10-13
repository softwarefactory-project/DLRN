#!/usr/bin/bash
set -eux

# Simple CI test to sanity test commits

# Display the current commit
git log -1

# Run unit tests
tox -epy27

# Run pep8 tests
tox -epep8

# Run bash unit tests
./scripts/run_sh_tests.sh

# Use the env setup by tox
set +u
. .tox/py27/bin/activate
set -u

# test that the mock command is present
type -p mock

# Build this if not building a specific project
PROJECT_TO_BUILD=python-glanceclient
PROJECT_TO_BUILD_MAPPED=$(./scripts/map-project-name $PROJECT_TO_BUILD)

# If this is a CI run for one of the distro repositories then we pre download it
# into the data directory, delorean wont change it because we are using --dev
if [ -n "$GERRIT_PROJECT" ] && [ "$GERRIT_PROJECT" != "openstack-packages/delorean" ] ; then
    # If building against a gerrit branch matching rpm-, pull the package from
    # that branch and set the baseurl accordingly
    if [[ "${GERRIT_BRANCH}" =~ rpm- ]]; then
        branch=$(sed "s/rpm-//" <<< "${GERRIT_BRANCH}")
        sed -i "s%source=.*%source=stable/${branch}%" projects.ini
        sed -i "s%baseurl=.*%baseurl=http://trunk.rdoproject.org/${branch}/centos7/%" projects.ini
    else
        # Otherwise baseurl is "master"
        sed -i "s%baseurl=.*%baseurl=http://trunk.rdoproject.org/centos7/%" projects.ini
    fi

    mkdir -p data/repos
    PROJECT_TO_BUILD=${GERRIT_PROJECT#*/}
    PROJECT_TO_BUILD_MAPPED=$(./scripts/map-project-name $PROJECT_TO_BUILD)
    PROJECT_DISTRO_DIR=${PROJECT_TO_BUILD_MAPPED}_distro
    git clone https://review.gerrithub.io/"$GERRIT_PROJECT" data/$PROJECT_DISTRO_DIR
    pushd data/$PROJECT_DISTRO_DIR
    git fetch https://review.gerrithub.io/$GERRIT_PROJECT $GERRIT_REFSPEC && git checkout FETCH_HEAD
    popd
fi

function copy_logs() {
    rsync -avzr data/repos logs/$DISTRO
}

function run_delorean() {
    export DISTRO="${1}"
    # Ensure we run against the right target
    sed -i -e "s%target=.*%target=${DISTRO}%" projects.ini
    # Run delorean
    delorean --config-file projects.ini --head-only --package-name $PROJECT_TO_BUILD_MAPPED --dev
    copy_logs
}

# If the commands below throws an error we still want the logs
trap copy_logs ERR

# Packages for fedora are only built for the master branch
[[ "${GERRIT_BRANCH}" == "master" ]] && run_delorean fedora
run_delorean centos
