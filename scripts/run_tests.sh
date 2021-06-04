#!/bin/bash
set -ex

# TODO(hguemar): have proper arguments parsing
# Usage with all supported arguments
# ./run_tests.sh <path_to_rdoinfo> <distro (either centos or fedora)> <baseurl to trunk repo> <tag (optional)>

# Simple script to test that DLRN works either locally or in a zuul environment
GIT_BASE_URL="https://review.rdoproject.org/r"
OPENSTACK_GIT_URL="https://opendev.org"
ZUUL3_HOME="${ZUUL3_HOME:-/home/zuul}"
ZUUL_CLONES_DIR="${ZUUL3_HOME}/src/review.rdoproject.org"
RDOINFO="${1:-$GIT_BASE_URL/rdoinfo}"
PYTHON_VERSION="${PYTHON_VERSION:-py27}"
# We want to make it work for both python2 and python3
if [ -x /usr/bin/python3 ]; then
    PYTHON=python3
else
    # Python 3 not available
    PYTHON=python2
fi

echo "Using $PYTHON as python interpreter"

function filterref(){
    PROJ=${1%%:*}
    echo $PROJ
}

# Display the current commit
git log -1

# Run bash unit tests
./scripts/run_sh_tests.sh

# Setup virtualenv with tox and use it
tox -e${PYTHON_VERSION} --notest
. .tox/${PYTHON_VERSION}/bin/activate

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

# If we are running under Zuul v3, we can find the rdoinfo git repo under /home/zuul
rm -rf /tmp/rdoinfo
if [ -d $ZUUL3_HOME -a -d $ZUUL_CLONES_DIR/rdoinfo ]; then
    ln -s $ZUUL_CLONES_DIR/rdoinfo /tmp/rdoinfo
else
    git clone ${RDOINFO} /tmp/rdoinfo
fi

# Prepare config
target="${2:-centos}"
baseurl="${3:-http://trunk.rdoproject.org/centos7/}"
src="master"
branch=""

if [ ${target} = "centos" ]; then
    baseurl_release="centos7"
    log_dir="centos"
elif [[ ${target} =~ "centos8" ]]; then
    baseurl_release="centos8"
    log_dir="centos8"
elif [[ ${target} =~ "centos9" ]]; then
    baseurl_release="centos9"
    log_dir="centos9"
fi

# If we're testing a commit on a specific branch, make sure we're using it
if [[ "${ZUUL_BRANCH}" =~ rpm- && "${ZUUL_BRANCH}" != "rpm-master" ]]; then
    branch=$(sed "s/rpm-//" <<< "${ZUUL_BRANCH}")
    # assume feature branch targeting master
    baseurl="http://trunk.rdoproject.org/${baseurl_release}-master/"
    src="${branch}"
    # for rdoinfo tags filter
    branch=""
    PROJECT_DISTRO_BRANCH=$ZUUL_BRANCH
# Add logic for new branches, *-rdo
elif [[ "${ZUUL_BRANCH}" =~ -rdo ]]; then
    branch=$(sed "s/-rdo//" <<< "${ZUUL_BRANCH}")
    baseurl="http://trunk.rdoproject.org/${branch}/${baseurl_release}/"
    src="stable/${branch}"
    PROJECT_DISTRO_BRANCH=$ZUUL_BRANCH
fi

# Update the configuration
tag=${4:-$branch}
sed -i "s%target=.*%target=${target}%" projects.ini
sed -i "s%source=.*%source=${src}%" projects.ini
sed -i "s%baseurl=.*%baseurl=${baseurl}%" projects.ini
sed -i "s%tags=.*%tags=${tag}%" projects.ini

# Prepare directories for distro repo
mkdir -p data/repos

# If the commands below throws an error we still want the logs
function copy_logs() {
    find data/repos -regex '.*\.log' -exec gzip {} \;
    mkdir -p logs
    rsync -avzr data/repos logs/$log_dir
    # Only copy the current symlink if it exists
    if [ -h data/repos/current ]; then
      rsync -avzrL data/repos/current logs/$log_dir
    fi
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
    if [ -d $ZUUL3_HOME -a -d $ZUUL_CLONES_DIR/$PROJECT_DISTRO ]; then
        ln -s $ZUUL_CLONES_DIR/$PROJECT_DISTRO data/$PROJECT_DISTRO_DIR
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
        UPSTREAM_URL_REDIRECTED=$(curl -Ls -w %{url_effective} -o /dev/null ${UPSTREAM_URL})
        UPSTREAM_PROJECT_NAME=${UPSTREAM_URL_REDIRECTED/https:\/\/opendev.org\//}
        # Only build in the check pipeline to avoid merging a change
        # in packaging that is dependent of an non merged upstream
        # change
        if [ "${ZUUL_PIPELINE}" == "check" ]; then
            rm -rf data/${PROJECT_TO_BUILD_MAPPED}
            git clone ${UPSTREAM_URL_REDIRECTED} "data/${PROJECT_TO_BUILD_MAPPED}"

            # We cannot run git review -d because we don't have an
            # available account. So we do the same using curl, jq and git.
            if [ "$branch" != "" ]; then
                REVIEW_BRANCH="stable%2F$branch"
            else
                REVIEW_BRANCH="master"
            fi

            JSON=$(curl -s -L https://review.opendev.org/changes/${UPSTREAM_PROJECT_NAME/\//%2F}~$REVIEW_BRANCH~$UPSTREAM_ID/revisions/current/review|sed 1d)
            COMMIT=$($PYTHON -c 'import json;import sys; s = json.loads(sys.stdin.read(-1)); print(s["current_revision"])' <<< $JSON)
            REF=$($PYTHON -c "import json;import sys; s = json.loads(sys.stdin.read(-1)); print(s['revisions']['$COMMIT']['ref'])" <<< $JSON)
            GERRIT_URL=$($PYTHON -c "import json;import sys; s = json.loads(sys.stdin.read(-1)); print(s['revisions']['$COMMIT']['fetch']['anonymous http']['url'])" <<< $JSON)
            pushd data/${PROJECT_TO_BUILD_MAPPED}
            if [ -n "$REF" -a "$REF" != null ]; then
                git fetch ${GERRIT_URL} $REF
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
