#!/bin/bash
set -ex

# TODO(hguemar): have proper arguments parsing
# Usage with all supported arguments
# ./run_tests.sh <path_to_rdoinfo> <distro (either centos or fedora)> <baseurl to trunk repo>

# Simple script to test that DLRN works either locally or in a zuul environment
GIT_BASE_URL="https://review.rdoproject.org/r/p"
OPENSTACK_GIT_URL="git://git.openstack.org"
RDOINFO="${1:-$GIT_BASE_URL/rdoinfo}"

function filterref(){
    PROJ=${1%%:*}
    echo $PROJ
}

# Display the current commit
git log -1

# Run bash unit tests
./scripts/run_sh_tests.sh

# Setup virtualenv with tox and use it
tox -epy27 --notest
. .tox/py27/bin/activate

# Default project to build
PROJECT_DISTRO="openstack/packstack-distgit"
PROJECT_DISTRO_BRANCH="rpm-master"

# If we're actually building for a Zuul project, build that unless it's DLRN
[[ ! -z "${ZUUL_PROJECT}" && "${ZUUL_PROJECT}" != "DLRN" ]] && PROJECT_DISTRO="${ZUUL_PROJECT}"

PROJECTS_TO_BUILD=""
if [[ ! -z "${ZUUL_CHANGES}" && "${ZUUL_PROJECT}" != "DLRN" ]]; then
  ZUUL_CHANGES=${ZUUL_CHANGES//^/ }
  for CHANGE in $ZUUL_CHANGES; do
    PROJ=$(filterref $CHANGE)
    # There may be non-distgit dependent changes, e.g. rdoinfo
    if [[ "${PROJ}" =~ '-distgit' ]]; then
      PROJECTS_TO_BUILD="$PROJECTS_TO_BUILD $PROJ"
    fi
  done
else
  PROJECTS_TO_BUILD=${PROJECT_DISTRO}
fi

# Fetch rdoinfo using zuul_cloner, if available
if type -p zuul-cloner; then
    zuul-cloner --workspace /tmp ${GIT_BASE_URL} rdoinfo
else
    rm -rf /tmp/rdoinfo
    git clone ${RDOINFO} /tmp/rdoinfo
fi

# Prepare config
target="${2:-centos}"
baseurl="${3:-http://trunk.rdoproject.org/centos7/}"
src="master"
branch=""

# If we're testing a commit on a specific branch, make sure we're using it
if [[ "${ZUUL_BRANCH}" =~ rpm- && "${ZUUL_BRANCH}" != "rpm-master" ]]; then
    branch=$(sed "s/rpm-//" <<< "${ZUUL_BRANCH}")
    if [[ "${branch}" = "liberty" || "${branch}" = "mitaka" ]]; then
        baseurl="http://trunk.rdoproject.org/${branch}/centos7/"
        src="stable/${branch}"
    else
        # assume feature branch targeting master
        baseurl="http://trunk.rdoproject.org/centos7-master/"
        src="${branch}"
        # for rdoinfo tags filter
        branch=""
    fi
    PROJECT_DISTRO_BRANCH=$ZUUL_BRANCH
# Add logic for new branches, *-rdo
elif [[ "${ZUUL_BRANCH}" =~ -rdo ]]; then
    branch=$(sed "s/-rdo//" <<< "${ZUUL_BRANCH}")
    baseurl="http://trunk.rdoproject.org/${branch}/centos7/"
    src="stable/${branch}"
    PROJECT_DISTRO_BRANCH=$ZUUL_BRANCH
fi

# Update the configuration
sed -i "s%target=.*%target=${target}%" projects.ini
sed -i "s%source=.*%source=${src}%" projects.ini
sed -i "s%baseurl=.*%baseurl=${baseurl}%" projects.ini
sed -i "s%tags=.*%tags=${branch}%" projects.ini

# Prepare directories for distro repo
mkdir -p data/repos

# If the commands below throws an error we still want the logs
function copy_logs() {
    mkdir -p logs
    rsync -avzr data/repos logs/$target
    rsync -avzrL data/repos/current logs/$target
}
trap copy_logs ERR EXIT

# Build all projects, hopefully the order given by Zuul was correct
PACKAGE_BUILD_LIST=""
for PROJECT_TO_BUILD in ${PROJECTS_TO_BUILD}; do
    PROJECT_DISTRO=$PROJECT_TO_BUILD
    # The rdoinfo project name isn't prefixed by openstack/ or suffixed by -distgit
    PROJECT_TO_BUILD=${PROJECT_DISTRO#*/}
    PROJECT_TO_BUILD=$(sed "s/-distgit//" <<< "${PROJECT_TO_BUILD}")
    # Map to rdoinfo
    # We have a special situation with Gnocchi pre-Queens. To detect it properly, we need a hack
    if [[ "$PROJECT_TO_BUILD" = "gnocchi" ]]; then
        if [[ "${branch}" = "newton" || "${branch}" = "ocata" || "${branch}" = "pike" ]]; then
            PROJECT_TO_BUILD="gnocchi-legacy"
        fi
    fi
    PROJECT_TO_BUILD_MAPPED=$(rdopkg findpkg $PROJECT_TO_BUILD -l /tmp/rdoinfo | grep ^name | awk '{print $2}')
    PROJECT_DISTRO_DIR=${PROJECT_TO_BUILD_MAPPED}_distro

    # Remove distro dir first for idempotency
    rm -rf data/$PROJECT_DISTRO_DIR

    # Clone distro repo
    if type -p zuul-cloner; then
        zuul-cloner --workspace data/ $GIT_BASE_URL $PROJECT_DISTRO --branch $PROJECT_DISTRO_BRANCH
        mv data/$PROJECT_DISTRO data/$PROJECT_DISTRO_DIR
    else
        # We're outside the gate, just do a regular git clone
        pushd data/
        git clone "${GIT_BASE_URL}/${PROJECT_DISTRO}" $PROJECT_DISTRO_DIR
        cd $PROJECT_DISTRO_DIR
        git checkout $PROJECT_DISTRO_BRANCH
        popd
    fi

    # Lookup if we need to extract an upstream review
    pushd data/${PROJECT_DISTRO_DIR}
    [ -n "$UPSTREAM_ID" ] || UPSTREAM_ID=$(git log -1|sed -ne 's/\s*Upstream-Id: //p')
    git log -1
    popd

    if [ -n "$UPSTREAM_ID" ]; then
        # Get upstream URL
        UPSTREAM_URL=$(rdopkg findpkg $PROJECT_TO_BUILD -l /tmp/rdoinfo | grep ^upstream | awk '{print $2}')
        UPSTREAM_PROJECT_NAME=$(basename ${UPSTREAM_URL})
        rm -rf data/${PROJECT_TO_BUILD_MAPPED}
        if type -p zuul-cloner; then
            # Only build in the check pipeline to avoid merging a change
            # in packaging that is dependent of an non merged upstream
            # change
            if [ "${ZUUL_PIPELINE}" = "check" ]; then
                zuul-cloner --workspace data/ $OPENSTACK_GIT_URL openstack/${UPSTREAM_PROJECT_NAME}
                mv data/openstack/${UPSTREAM_PROJECT_NAME} data/${PROJECT_TO_BUILD_MAPPED}
            else
                NOT_EXTRACTED=1
            fi
         else
            git clone ${UPSTREAM_URL} "data/${PROJECT_TO_BUILD_MAPPED}"
        fi
        if [ -z "$NOT_EXTRACTED" ]; then
            # We cannot run git review -d because we don't have an
            # available account. So we do the same using curl, jq and git.
            JSON=$(curl -s -L https://review.openstack.org/changes/$UPSTREAM_ID/revisions/current/review|sed 1d)
            COMMIT=$(python -c 'import json;import sys; s = json.loads(sys.stdin.read(-1)); print s["revisions"].keys()[0]' <<< $JSON)
            REF=$(python -c "import json;import sys; s = json.loads(sys.stdin.read(-1)); print s['revisions']['$COMMIT']['ref']" <<< $JSON)
            pushd data/${PROJECT_TO_BUILD_MAPPED}
            if [ -n "$REF" -a "$REF" != null ]; then
                git fetch ${UPSTREAM_URL} $REF
                git checkout FETCH_HEAD
            fi
            git log -1
            popd
        fi
    fi
    PACKAGE_BUILD_LIST="$PACKAGE_BUILD_LIST --package-name $PROJECT_TO_BUILD_MAPPED"
done

# Run DLRN
dlrn --head-only $PACKAGE_BUILD_LIST --dev --local --info-repo /tmp/rdoinfo --verbose-build --order
copy_logs
# Clean up mock cache, just in case there is a change for the next run
mock -r data/dlrn-1.cfg --scrub=all
