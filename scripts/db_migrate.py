#!/usr/bin/env python
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

import argparse
import os
import sys

from tempfile import mkstemp

from dlrn.db import getSession
from dlrn.utils import loadYAML
from dlrn.utils import saveYAML


def migrate_db(source_string, dest_string):
    osfd, tmpfilename = mkstemp()
    session = getSession(source_string)
    saveYAML(session, tmpfilename)
    session.close()
    session2 = getSession(dest_string)
    loadYAML(session2, tmpfilename)
    os.remove(tmpfilename)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source',
                        help="SQLAlchemy connection string for the source"
                             "database.",
                        required=True)
    parser.add_argument('--dest',
                        help="SQLAlchemy connection string for the"
                             "destination database.",
                        required=True)

    options, args = parser.parse_known_args(sys.argv[1:])

    migrate_db(options.source, options.dest)


if __name__ == '__main__':
    main()
    exit(0)
