#!/usr/bin/env python
# A script that queries the database for commit/build information, determines
# when a build ended and prints a pretty table containing build information,
# including the build duration.
#
# Usage: ./profiler.py /home/centos-master/

from __future__ import print_function

import os
import sys

from dlrn.db import getSession, Commit
from datetime import datetime
from prettytable import PrettyTable


def format_time(timestamp, format="%Y-%m-%d %H:%M:%S"):
    return timestamp.strftime(format)

# Minimal validation but expect something like /home/centos-master
if len(sys.argv) < 2:
    sys.exit('Usage: %s </home/centos-something>' % sys.argv[0])

worker_path = sys.argv[1]
if not os.path.exists(worker_path):
    sys.exit('Usage: %s </home/centos-something>' % sys.argv[0])

# We assume the location of database and repositories from the worker location
database = os.path.join(worker_path, 'dlrn/commits.sqlite')
repo_root = os.path.join(worker_path, 'data/repos')

# Open a database session
session = getSession('sqlite:///%s' % database)

# Query the last 100 builds for their data
query = session.query(Commit).order_by(Commit.dt_build).limit(100)
table = PrettyTable(["project", "start", "end", "duration", "repository"])
for result in query:
    project = result.project_name
    start = datetime.fromtimestamp(result.dt_build)
    hashed_dir = result.getshardedcommitdir()
    repository = os.path.join(repo_root, hashed_dir)

    # delorean.repo is one of the files that is created last, use it's mtime
    # to determine when the build ended
    file = os.path.join(repository, 'delorean.repo')
    end = datetime.fromtimestamp(os.stat(file).st_mtime)
    duration = end - start

    table.add_row([project,
                   format_time(start),
                   format_time(end),
                   duration,
                   hashed_dir])

print(table)
