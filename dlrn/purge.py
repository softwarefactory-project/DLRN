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
import logging
import os
import shutil
import sys

from datetime import datetime
from datetime import timedelta
from six.moves import configparser
from time import mktime

from dlrn.db import Commit
from dlrn.db import getCommits
from dlrn.db import getSession

FLAG_PURGED = 0x2

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("dlrn-purge")
logger.setLevel(logging.INFO)


def purge():
    parser = argparse.ArgumentParser()
    # Some of the non-positional arguments are required, so change the text
    # saying "optional arguments" to just "arguments":
    parser._optionals.title = 'arguments'

    parser.add_argument('--config-file',
                        help="Config file (required)", required=True)
    parser.add_argument('--older-than',
                        help="How old commits need to be purged "
                             "(in days).", required=True)
    parser.add_argument('-y', help="Answer \"yes\" to any questions",
                        action="store_true")
    parser.add_argument('--dry-run', help="Do not change anything, show"
                        "what changes would be made",
                        action="store_true")

    options, args = parser.parse_known_args(sys.argv[1:])

    cp = configparser.RawConfigParser()
    cp.read(options.config_file)

    timeparsed = datetime.now() - timedelta(days=int(options.older_than))

    if options.y is False:
        ans = raw_input(("Remove all data before %s, correct? [N/y] " %
                        timeparsed.ctime()))
        if ans.lower() != "y":
            return

    session = getSession('sqlite:///commits.sqlite')

    # To remove builds we have to start at a point in time and move backwards
    # builds with no build date are also purged as these are legacy
    # All repositories can have the repodata directory and symlinks purged
    # But we must keep the rpms files of the most recent successful build of
    # each project as other symlinks not being purged will be pointing to them.
    topurge = getCommits(session,
                         limit=0,
                         before=int(mktime(timeparsed.timetuple()))
                         ).all()

    fullpurge = []
    for commit in topurge:
        if commit.flags & FLAG_PURGED:
            continue
        datadir = os.path.join(cp.get('DEFAULT', 'datadir'), "repos",
                               commit.getshardedcommitdir())
        if commit.project_name not in fullpurge and commit.status == "SUCCESS":
            # So we have not removed any commit from this project yet, and it
            # is successful. Is it the newest one?
            previouscommits = getCommits(session,
                                         project=commit.project_name,
                                         since=commit.dt_build,
                                         with_status='SUCCESS').count()

            if previouscommits == 0:
                logger.info("Keeping old commit for %s" % commit.project_name)
                continue  # this is the newest commit for this project, keep it

            try:
                for entry in os.listdir(datadir):
                    entry = os.path.join(datadir, entry)
                    if entry.endswith(".rpm") and not os.path.islink(entry):
                        continue
                    if os.path.isdir(entry):
                        if options.dry_run is False:
                            shutil.rmtree(entry)
                        else:
                            logger.info("Remove %s" % entry)
                    else:
                        if options.dry_run is False:
                            os.unlink(entry)
                        else:
                            logger.info("Delete %s" % entry)
            except OSError:
                logger.warning("Cannot access directory %s for purge,"
                               " ignoring." % datadir)
            fullpurge.append(commit.project_name)
            commit.flags |= FLAG_PURGED
            if options.dry_run is False:
                shutil.rmtree(datadir)
            else:
                logger.info("Remove %s" % datadir)
        else:
            # If the commit was not successful, we need to be careful not to
            # remove the directory if there was a successful build
            if commit.status != "SUCCESS":
                othercommits = session.query(Commit).filter(
                    Commit.project_name == commit.project_name,
                    Commit.commit_hash == commit.commit_hash,
                    Commit.status == 'SUCCESS').count()

                if othercommits == 0:
                    if options.dry_run is False:
                        shutil.rmtree(datadir)
                    else:
                        logger.info("Remove %s" % datadir)
            else:
                    if options.dry_run is False:
                        shutil.rmtree(datadir)
                    else:
                        logger.info("Remove %s" % datadir)
            commit.flags |= FLAG_PURGED
    if options.dry_run is False:
        session.commit()
