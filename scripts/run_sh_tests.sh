#!/usr/bin/bash

set -eu

source ./scripts/common-functions

# UPSTREAMVERSION EXPECTED_UPSTREAMVERSION EXPECTED_VERSION  EXPECTED_RELEASE
function test_setvr(){
    # Set release date to a hardcoded time we can test for
    export RELEASE_DATE=20150102034455
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

# Test a good representation of known use cases
unset RELEASE_NUMBERING
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
test_setvr 1.8.0.pre               1.8.0.pre               1.8.0      0.20150102034455.shortsha
test_setvr 1.8.0.pre.1             1.8.0.pre.1             1.8.0      0.20150102034455.shortsha

# Test with the new release numbering scheme
unset TARBALL
export RELEASE_NUMBERING="0.1.date.hash"
test_setvr 1.0.0-d7f1b849          1.0.0-d7f1b849          1.0.0      0.1.20150102034455.shortsha
test_setvr 0.10.1.11.ga5f0e3c      0.10.1.11.ga5f0e3c      0.10.1.11  0.1.20150102034455.shortsha
test_setvr 0.0.2.dev7              0.0.2.dev7              0.0.2      0.1.20150102034455.shortsha
test_setvr 13.0.1.dev3             13.0.1.dev3             13.0.1     0.1.20150102034455.shortsha
test_setvr 0.0.9                   0.0.9                   0.0.9      0.1.20150102034455.shortsha
test_setvr 0.19.1.dev25            0.19.1.dev25            0.19.1     0.1.20150102034455.shortsha
test_setvr 0.6.0                   0.6.0                   0.6.0      0.1.20150102034455.shortsha
test_setvr 1.0.0.0b2.dev15         1.0.0.0b2.dev15         1.0.0      0.1.20150102034455.shortsha
test_setvr 1.0.0.0rc2.dev128       1.0.0.0rc2.dev128       1.0.0      0.1.20150102034455.shortsha
test_setvr 2015.1.0.dev47          2015.1.0.dev47          2015.1.0   0.1.20150102034455.shortsha
test_setvr 2015.1.dev1604.g34cf1e3 2015.1.dev1604.g34cf1e3 2015.1     0.1.20150102034455.shortsha
test_setvr 2015.2.1                2015.2.1                2015.2.1   0.1.20150102034455.shortsha
test_setvr 8.0.0.0b2.dev268        8.0.0.0b2.dev268        8.0.0      0.1.20150102034455.shortsha
test_setvr 2.0.0.0b4.dev15         2.0.0.0b4.dev15         2.0.0      0.1.20150102034455.shortsha
test_setvr 7.0.0.0a1.dev1          7.0.0.0a1.dev1          7.0.0      0.1.20150102034455.shortsha
# Do not display known WARNING message
test_setvr eb6dbe2                 eb6dbe2                 0.0.1      0.1.20150102034455.shortsha > /dev/null
test_setvr 2015.1.9-13-g53b605d    2015.1.9-13-g53b605d    2015.1.9   0.1.20150102034455.shortsha
# This one tests a special case for python-alembic
TARBALL=alembic-0.0.9.dev0.tar.gz \
test_setvr 0.0.9                   0.0.9.dev0              0.0.9      0.1.20150102034455.shortsha
test_setvr 1.8.0.pre               1.8.0.pre               1.8.0      0.1.20150102034455.shortsha
test_setvr 1.8.0.pre.1             1.8.0.pre.1             1.8.0      0.1.20150102034455.shortsha

# Use a minor.date.hash release numbering scheme
export RELEASE_NUMBERING="minor.date.hash"
export RELEASE_MINOR=4
test_setvr 1.0.0-d7f1b849          1.0.0-d7f1b849          1.0.0      4.20150102034455.shortsha
test_setvr 0.10.1.11.ga5f0e3c      0.10.1.11.ga5f0e3c      0.10.1.11  4.20150102034455.shortsha
test_setvr 0.0.2.dev7              0.0.2.dev7              0.0.2      4.20150102034455.shortsha
test_setvr 13.0.1.dev3             13.0.1.dev3             13.0.1     4.20150102034455.shortsha
test_setvr 0.0.9                   0.0.9                   0.0.9      4.20150102034455.shortsha
test_setvr 0.19.1.dev25            0.19.1.dev25            0.19.1     4.20150102034455.shortsha
test_setvr 0.6.0                   0.6.0                   0.6.0      4.20150102034455.shortsha
test_setvr 1.0.0.0b2.dev15         1.0.0.0b2.dev15         1.0.0      4.20150102034455.shortsha
test_setvr 1.0.0.0rc2.dev128       1.0.0.0rc2.dev128       1.0.0      4.20150102034455.shortsha
test_setvr 2015.1.0.dev47          2015.1.0.dev47          2015.1.0   4.20150102034455.shortsha
test_setvr 2015.1.dev1604.g34cf1e3 2015.1.dev1604.g34cf1e3 2015.1     4.20150102034455.shortsha
test_setvr 2015.2.1                2015.2.1                2015.2.1   4.20150102034455.shortsha
test_setvr 8.0.0.0b2.dev268        8.0.0.0b2.dev268        8.0.0      4.20150102034455.shortsha
test_setvr 2.0.0.0b4.dev15         2.0.0.0b4.dev15         2.0.0      4.20150102034455.shortsha
test_setvr 7.0.0.0a1.dev1          7.0.0.0a1.dev1          7.0.0      4.20150102034455.shortsha
# Do not display known WARNING message
test_setvr eb6dbe2                 eb6dbe2                 0.0.1      4.20150102034455.shortsha > /dev/null
test_setvr 2015.1.9-13-g53b605d    2015.1.9-13-g53b605d    2015.1.9   4.20150102034455.shortsha
# This one tests a special case for python-alembic
TARBALL=alembic-0.0.9.dev0.tar.gz \
test_setvr 0.0.9                   0.0.9.dev0              0.0.9      4.20150102034455.shortsha
test_setvr 1.8.0.pre               1.8.0.pre               1.8.0      4.20150102034455.shortsha
test_setvr 1.8.0.pre.1             1.8.0.pre.1             1.8.0      4.20150102034455.shortsha
