#!/usr/bin/bash
set -eux

# Simple CI test to sanity test commits

# Make sure docker is running
sudo systemctl start docker

# Display the current commit
git log -1

# Build this if not building a specific project
PROJECT_TO_BUILD=python-keystoneclient

# Run unit tests
tox -epy27

# Run pep8 tests
tox -epep8

# Create build images, this will endup being a noop on hosts where
# it was already run if the dockerfile hasn't changed
./scripts/create_build_image.sh fedora
./scripts/create_build_image.sh centos

# If this is a CI run for one of the spec files then we pre download it
# into the data directory, delorean wont change it because we are using --dev
if [ -n "$GERRIT_PROJECT" ] && [ "$GERRIT_PROJECT" != "openstack-packages/delorean" ] ; then
    mkdir -p data/repos
    PROJECT_TO_BUILD=${GERRIT_PROJECT#*/}
    PROJECT_SPEC_DIR=${PROJECT_TO_BUILD}_spec
    git clone https://review.gerrithub.io/"$GERRIT_PROJECT" data/$PROJECT_SPEC_DIR
    pushd data/$PROJECT_SPEC_DIR
    git fetch https://review.gerrithub.io/$GERRIT_PROJECT $GERRIT_REFSPEC && git checkout FETCH_HEAD
    popd
fi


# And Run delorean against a project
set +u
. .tox/py27/bin/activate
set -u
delorean --config-file projects.ini --head-only --package-name $(./scripts/map-project-name $PROJECT_TO_BUILD) --dev

# Copy files to be archived
cp -r data/repos logs/fedora

# Switch to a centos target
sed -i -e 's%target=.*%target=centos%' projects.ini
sed -i -e 's%baseurl=.*%baseurl=http://104.130.230.24/centos70%' projects.ini

# And run delorean again, for the moment we mask failures i.e. report only until we're sure all the specs run
delorean --config-file projects.ini --head-only --package-name $(./scripts/map-project-name $PROJECT_TO_BUILD) --dev

# Copy files to be archived
cp -r data/repos logs/centos
