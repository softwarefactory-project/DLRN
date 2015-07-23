#!/usr/bin/bash

set -eu

source ./scripts/common-functions

# UPSTREAMVERSION EXPECTED_UPSTREAMVERSION EXPECTED_VERSION  EXPECTED_RELEASE
function test_setvr(){
    # Set date to return a hardcoded time we can test for
    function date(){ $(which --skip-functions date) --date='2015/1/2 3:44:55' $@ ; }
    VERSION=
    RELEASE=
    setversionandrelease $1
    unset -f date
    if [ $UPSTREAMVERSION != $2 ] || [ $VERSION != $3 ] || [ $RELEASE != $4 ] ; then
        shift
        echo "$0 FAILED EXPECTED: $@ (GOT: $UPSTREAMVERSION $VERSION $RELEASE)"
        return 1
    fi
    return 0
}

# Test a good representation of known use cases
test_setvr 1.0.0-d7f1b849          1.0.0-d7f1b849          1.0.0      d7f1b849
test_setvr 0.10.1.11.ga5f0e3c      0.10.1.11.ga5f0e3c      0.10.1.11  ga5f0e3c
test_setvr 0.0.2.dev7              0.0.2.dev7              0.0.2      dev7
test_setvr 0.0.9                   0.0.9                   0.0.9      0.99.20150102.0344git
test_setvr 0.19.1.dev25            0.19.1.dev25            0.19.1     dev25
test_setvr 0.6.0                   0.6.0                   0.6.0      0.99.20150102.0344git
test_setvr 1.0.0.0b2.dev15         1.0.0.0b2.dev15         1.0.0.0b2  dev15
test_setvr 1.0.0.0rc2.dev128       1.0.0.0rc2.dev128       1.0.0.0rc2 dev128
test_setvr 2015.1.0.dev47          2015.1.0.dev47          2015.1.0   dev47
test_setvr 2015.1.dev1604.g34cf1e3 2015.1.dev1604.g34cf1e3 2015.1     dev1604.g34cf1e3
test_setvr 2015.2.1                2015.2.1                2015.2.1   0.99.20150102.0344git
test_setvr 3.0.1a                  3.0.1a                  3.0        1a
test_setvr 8.0.0.0b2.dev268        8.0.0.0b2.dev268        8.0.0.0b2  dev268
test_setvr eb6dbe2                 eb6dbe2                 0.0.1      eb6dbe2
test_setvr 2015.1.9-13-g53b605d    2015.1.9-13-g53b605d    2015.1.9   13.g53b605d
# This one tests a special case for python-alembic
TARBALL=0.0.9dev.tar \
test_setvr 0.0.9                   0.0.9dev                   0.0.9      0.99.20150102.0344git
