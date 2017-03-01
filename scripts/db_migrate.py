#!/usr/bin/env python
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

