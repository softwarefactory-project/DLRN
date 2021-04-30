#!/bin/bash -xe

set -o pipefail

# FIXME(hguemar): we need to document all parameters passed to this script
shift   # First parameter is TARGET, not needed here

source $(dirname $0)/common-functions

exec &> >(tee "${OUTPUT_DIRECTORY}/rpmbuild.log") 2>&1
set -x

for FILE in {test-,}requirements.txt
do
    if [ -f ${FILE} ]
    then
        sed -i "s/; *python_version.*[!=<>]=\?.*//g" ${FILE}
        sed -i "s/; *sys_platform.*[!=<>]=\?.*//g" ${FILE}
    fi
done

cleanup_sdist

detect_python
setup_mock

if [ -z "$DLRN_KEEP_SPEC_AS_IS" ]; then
    # As a first step, calculate version and release
    detect_version_and_release

    # As a second step, generate tarball
    if [ -r setup.py -a ! -r metadata.json ]; then
        SOURCETYPE='tarball'
        /usr/bin/mock $MOCKOPTS --chroot "cd /var/tmp/pkgsrc && (([ -x /usr/bin/python3 ] && python3 setup.py sdist) || python setup.py sdist)"
        /usr/bin/mock $MOCKOPTS --copyout /var/tmp/pkgsrc/dist ${TOP_DIR}/dist
    elif [ -r *.gemspec ]; then
        SOURCETYPE='gem'
        /usr/bin/mock $MOCKOPTS --chroot "cd /var/tmp/pkgsrc && gem build $GEMSPEC"
        /usr/bin/mock $MOCKOPTS --copyout /var/tmp/pkgsrc/$PROJECT-$VERSION.gem ./$PROJECT-$VERSION.gem
    else
        SOURCETYPE='tarball'
        if [ -r metadata.json ]; then
            # Detect if this is an OpenStack puppet module
            # We know OpenStack puppet modules have a common style for metadata.json
            MODULE_NAME=$($PYTHON -c "import json; print(json.loads(open('metadata.json').read(-1))['name'])")
            if [[ "$MODULE_NAME" =~ openstack-* ]]; then
                TARNAME=$MODULE_NAME
            else
                TARNAME=$(git remote -v|head -1|awk '{print $2;}'|sed 's@.*/@@;s@\.git$@@')
            fi
        elif [ -r Modulefile ]; then
            TARNAME=$(git remote -v|head -1|awk '{print $2;}'|sed 's@.*/@@;s@\.git$@@')
        elif [ -r Kconfig -a -r Kbuild ]; then
            TARNAME=linux
        else
            TARNAME=${PROJECT_NAME}
        fi
        tar zcvf ${TOP_DIR}/${VERSION}.tar.gz --exclude=.git --transform="s@${PWD#/}@${TARNAME}-${version}@" --show-transformed-names $PWD
        mkdir -p ${TOP_DIR}/dist
        mv ${TOP_DIR}/${VERSION}.tar.gz ${TOP_DIR}/dist/
    fi

    if [ "$SOURCETYPE" == 'gem' ]; then
        SOURCE=$(ls -l | grep '.gem$' | awk '{print $9}')
        SOURCEEXT='.gem'
        SOURCEPATH=$SOURCE
    else
        SOURCE=$(ls ${TOP_DIR}/dist | grep '.tar.gz')
        SOURCEEXT='.tar.gz'
        SOURCEPATH="${TOP_DIR}/dist/$SOURCE"
    fi
    SOURCEWITHREL=$(basename $SOURCE $SOURCEEXT)-$RELEASE$SOURCEEXT
    mv $SOURCEPATH ${TOP_DIR}/SOURCES/$SOURCEWITHREL
fi

cd ${DISTGIT_DIR}
cp -a * ${TOP_DIR}/SOURCES/
cp *.spec ${TOP_DIR}/SPECS/
cd ${TOP_DIR}/SPECS/

if [ -z "$DLRN_KEEP_SPEC_AS_IS" ]; then
    grep -qc "^%define upstream_version.*" *.spec && \
        sed -i -e "s/^%define upstream_version.*/%define upstream_version $UPSTREAMVERSION/" *.spec || \
        sed -i -e "1i%define upstream_version $UPSTREAMVERSION\\" *.spec
    grep -qc "^%global dlrn .*" *.spec && \
        sed -i -e "s/^%global dlrn .*/%global dlrn 1/" *.spec || \
        sed -i -e "1i%global dlrn 1\\" *.spec
    grep -qc "^%global dlrn_nvr .*" *.spec && \
        sed -i -e "s/^%global dlrn_nvr .*/%global dlrn_nvr $(basename $SOURCEWITHREL $SOURCEEXT)/" *.spec || \
        sed -i -e "1i%global dlrn_nvr $(basename $SOURCEWITHREL $SOURCEEXT)\\" *.spec
    sed -i -e "s/UPSTREAMVERSION/$UPSTREAMVERSION/g" *.spec
    set_nvr_in_spec
    if [ "$DLRN_KEEP_TARBALL" != "1" ]; then
        sed -i -e "s/^\(Source\|Source0\):.*/\1: $SOURCEWITHREL/" *.spec
    fi
    if [ "$DLRN_KEEP_CHANGELOG" != "1" ]; then
        sed -i -e '/^%changelog.*/q' *.spec
    fi
fi
cat *.spec
spectool -g -C ${TOP_DIR}/SOURCES *.spec
/usr/bin/mock --buildsrpm ${MOCKOPTS} --spec *.spec --sources=${TOP_DIR}/SOURCES

