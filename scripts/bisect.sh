#!/bin/bash
#
# Copyright (C) 2017 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# script to run in a git bisect for compilation issues with dlrn

set -e

if [ $# -lt 4 ]; then
    echo "Usage: $0 <dlrn config file> <project name> <good sha1> <bad sha1> [<dlrn extra args>]" 1>&2
    exit 1
fi

conf=$1
proj=$2
good=$3
bad=$4
shift 4
args="$@"

if [ ! -r $conf ]; then
    echo "Unable to read dlrn configuration file $conf" 1>&2
    exit 1
fi

if ! type -p dlrn; then
    echo "dlrn command not found in path" 1>&2
    exit 1
fi

# verify that the project is managed by dlrn

eval $(grep '^datadir=' $conf)

if [ -z "$datadir" ]; then
    echo "Unable to read datadir from $conf" 1>&2
    exit 1
fi

echo "Checking $proj"
dlrn --config $conf --package-name $proj $args --run /bin/true

cd $datadir/$proj

# create the compilation script

executor=$(mktemp)
chmod +x $executor

logdir=$(mktemp -d)

[ -d $logdir -a -w $logdir ]

echo "dlrn log in $logdir"

cleanup(){
    rm -f $executor
}

trap cleanup 0

cat > $executor <<EOF
#!/bin/bash

exec > $logdir/\$(git rev-parse HEAD) 2>&1

# we are in repos/<git dir>
cd ../..

dlrn --config $conf --dev --local --package-name $proj $args

exit $?
EOF

# launch the git bisect process

git bisect reset || :
git bisect start
git bisect good $good
git bisect bad $bad
git bisect run $executor
git bisect visualize

# bisect.sh ends here
