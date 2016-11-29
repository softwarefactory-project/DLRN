#!/usr/bin/bash

set -eu

source ./scripts/common-functions

# UPSTREAMVERSION EXPECTED_UPSTREAMVERSION EXPECTED_VERSION  EXPECTED_RELEASE
function test_setvr(){
    # Set date to return a hardcoded time we can test for
    function date(){ $(which --skip-functions date) --date='2015/1/2 3:44:55' $@ ; }
    VERSION=
    RELEASE=
    setversionandrelease $1 shortsha
    unset -f date
    if [ $UPSTREAMVERSION != $2 ] || [ $VERSION != $3 ] || [ $RELEASE != $4 ] ; then
        shift
        echo "$0 FAILED EXPECTED: $@ (GOT: $UPSTREAMVERSION $VERSION $RELEASE)"
        return 1
    fi
    return 0
}

# STRING_TO_TEST EXPECTED_PKG_NAME
function test_rdopkg_findpkg(){
    PKG_NAME=$(rdopkg findpkg $1 | grep ^name: | awk '{print $2}')
    if [ $2 != $PKG_NAME ]; then
        echo "$0 FAILED EXPECTED: $@ (GOT: $PKG_NAME)"
        return 1
    fi
    return 0
}

# Test a good representation of known use cases
test_setvr 1.0.0-d7f1b849          1.0.0-d7f1b849          1.0.0      0.20150102034455.shortsha
test_setvr 0.10.1.11.ga5f0e3c      0.10.1.11.ga5f0e3c      0.10.1.11  0.20150102034455.shortsha
test_setvr 0.0.2.dev7              0.0.2.dev7              0.0.2      0.20150102034455.shortsha
test_setvr 13.0.1.dev3             13.0.1.dev3             13.0.1     0.20150102034455.shortsha
test_setvr 0.0.9                   0.0.9                   0.0.9      0.20150102034455.shortsha
test_setvr 0.19.1.dev25            0.19.1.dev25            0.19.1     0.20150102034455.shortsha
test_setvr 0.6.0                   0.6.0                   0.6.0      0.20150102034455.shortsha
test_setvr 1.0.0.0b2.dev15         1.0.0.0b2.dev15         1.0.0      0.20150102034455.shortsha
test_setvr 1.0.0.0rc2.dev128       1.0.0.0rc2.dev128       1.0.0      0.20150102034455.shortsha
test_setvr 2015.1.0.dev47          2015.1.0.dev47          2015.1.0   0.20150102034455.shortsha
test_setvr 2015.1.dev1604.g34cf1e3 2015.1.dev1604.g34cf1e3 2015.1     0.20150102034455.shortsha
test_setvr 2015.2.1                2015.2.1                2015.2.1   0.20150102034455.shortsha
test_setvr 8.0.0.0b2.dev268        8.0.0.0b2.dev268        8.0.0      0.20150102034455.shortsha
test_setvr 2.0.0.0b4.dev15         2.0.0.0b4.dev15         2.0.0      0.20150102034455.shortsha
test_setvr 7.0.0.0a1.dev1          7.0.0.0a1.dev1          7.0.0      0.20150102034455.shortsha
# Do not display known WARNING message
test_setvr eb6dbe2                 eb6dbe2                 0.0.1      0.20150102034455.shortsha > /dev/null
test_setvr 2015.1.9-13-g53b605d    2015.1.9-13-g53b605d    2015.1.9   0.20150102034455.shortsha
# This one tests a special case for python-alembic
TARBALL=alembic-0.0.9.dev0.tar.gz \
test_setvr 0.0.9                   0.0.9.dev0              0.0.9      0.20150102034455.shortsha

# rdopkg findpkg tests
test_rdopkg_findpkg glance                          openstack-glance
test_rdopkg_findpkg puppet-glance                   puppet-glance
test_rdopkg_findpkg puppet/puppet-glance            puppet-glance
test_rdopkg_findpkg glanceclient                    python-glanceclient
test_rdopkg_findpkg openstack/glanceclient-distgit  python-glanceclient
test_rdopkg_findpkg python-glanceclient             python-glanceclient
