#!/usr/bin/bash
set -eux

# Simple CI test to sanity test commits

# Make sure docker is running
sudo systemctl start docker

# Display the current commit
git log -1

# Set up rdoinfo
# TODO(derekh): Remove this once we're using rdopkg
git clone https://github.com/redhat-openstack/rdoinfo.git --depth 1
export PYTHONPATH=rdoinfo

# Run unit tests
tox -epy27

# Run pep8 tests
tox -epep8

# Create a build image
./scripts/create_build_image.sh fedora

# And Run delorean against a project
set +u
. .tox/py27/bin/activate
delorean --config-file projects.ini --info-file ./rdoinfo/rdo.yml --head-only --package-name python-keystoneclient --dev
