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
import glob
import logging
import os
import shutil
import sys

from datetime import datetime
from datetime import timedelta
from six.moves import configparser
from six.moves import input
from time import mktime

from dlrn.config import setup_logging
from dlrn.db import closeSession
from dlrn.db import Commit
from dlrn.db import getCommits
from dlrn.db import getSession
from dlrn.db import Promotion
from dlrn.utils import get_component_list

FLAG_PURGED = 0x2

logger = logging.getLogger("dlrn-purge")


def is_commit_in_dirs(commit, dirlist, basedir, component_list=None):
    if dirlist is None:
        return False
    if commit.artifacts is None:
        return False
    directories = dirlist.split(',')
    rpms = []
    for rpm in commit.artifacts.split(','):
        rpms.append(rpm.split('/')[-1])

    for rpm in rpms:
        for directory in directories:
            if os.path.exists(os.path.join(directory, rpm)):
                return True
            # If using components, search for the relative component paths too
            if component_list:
                relpath = os.path.relpath(directory, basedir)
                for component in component_list:
                    newpath = os.path.join(basedir, 'component', component,
                                           relpath)
                    if os.path.exists(os.path.join(newpath, rpm)):
                        return True
    return False


def purge_promoted_hashes(config, timestamp, dry_run=True):
    session = getSession(config.get('DEFAULT', 'database_connection'))
    basedir = os.path.join(config.get('DEFAULT', 'datadir'), 'repos')
    reponame = config.get('DEFAULT', 'reponame')

    # Get list of all promote names
    all_promotions = session.query(Promotion).\
        distinct(Promotion.promotion_name).\
        group_by(Promotion.promotion_name).all()
    closeSession(session)

    promotion_list = ['current', 'consistent']
    for prom in all_promotions:
        promotion_list.append(prom.promotion_name)

    logger.debug("Promotion list: %s" % promotion_list)

    # Now go through all directories
    for prom in promotion_list:
        directory = os.path.join(basedir, prom)
        logger.info("Looking into directory: %s" % directory)
        if os.path.islink(os.path.join(directory, reponame + '.repo')):
            protected_path = os.path.dirname(
                os.path.realpath(os.path.join(directory, reponame + '.repo')))
        else:
            logger.warning('No symlinks at %s' % directory)
            protected_path = ''

        logger.debug("Setting protected path: %s" % protected_path)
        # We have to traverse a 3-level hash structure
        # Not deleting the first two levels (xx/yy), just the final level,
        # where the files are located
        for path in glob.glob('%s/??/??/*' % directory):
            if os.path.isdir(path):
                dirstats = os.stat(path)
                if timestamp > dirstats.st_mtime:
                    if os.path.realpath(path) == protected_path:
                        logger.info('Not deleting %s, it is protected' % path)
                        continue
                    logger.info("Remove %s" % path)
                    if not dry_run:
                        shutil.rmtree(path, ignore_errors=True)


def purge():
    parser = argparse.ArgumentParser()
    # Some of the non-positional arguments are required, so change the text
    # saying "optional arguments" to just "arguments":
    parser._optionals.title = 'arguments'

    parser.add_argument('--config-file',
                        help="Config file (required)", required=True)
    parser.add_argument('--older-than',
                        help="Purge builds older than provided value"
                             " (in days).", required=True)
    parser.add_argument('-y', help="Answer \"yes\" to any questions",
                        action="store_true")
    parser.add_argument('--dry-run', help="Do not change anything, show"
                        " what changes would be made",
                        action="store_true")
    parser.add_argument('--exclude-dirs', help="Do not remove commits whose"
                        " packages are included in one of the specifided"
                        " directories (comma-separated list).")
    parser.add_argument('--debug', action='store_true',
                        help="Print debug logs")

    options = parser.parse_args(sys.argv[1:])

    setup_logging(options.debug)

    cp = configparser.RawConfigParser()
    cp.read(options.config_file)

    timeparsed = datetime.now() - timedelta(days=int(options.older_than))

    if options.y is False:
        ans = input(("Remove all data before %s, correct? [N/y] " %
                     timeparsed.ctime()))
        if ans.lower() != "y":
            return

    session = getSession(cp.get('DEFAULT', 'database_connection'))
    try:
        use_components = cp.getboolean('DEFAULT', 'use_components')
    except ValueError:
        use_components = False
    basedir = os.path.abspath(os.path.join(cp.get('DEFAULT', 'datadir'),
                                           'repos'))
    if use_components:
        component_list = get_component_list(session)
    else:
        component_list = None
    logger.debug("Used components: %s" % component_list)

    # To remove builds we have to start at a point in time and move backwards
    # builds with no build date are also purged as these are legacy
    # All repositories can have the repodata directory and symlinks purged
    # But we must keep the rpm files of the most recent successful build of
    # each project as other symlinks not being purged will be pointing to them.
    topurge = getCommits(session,
                         limit=0,
                         before=int(mktime(timeparsed.timetuple()))
                         ).all()

    logger.debug("Commmits from %s days ago: %s" % (options.older_than,
                                                    topurge))

    fullpurge = []
    for commit in topurge:
        if commit.flags & FLAG_PURGED:
            logger.debug("Commit %s was purged" % commit)
            continue

        if is_commit_in_dirs(commit, options.exclude_dirs, basedir,
                             component_list=component_list):
            # The commit RPMs are in one of the directories
            # that should not be touched.
            logger.info("Ignoring commit %s for %s, it is in one of the"
                        " excluded directories" % (commit.id,
                                                   commit.project_name))
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
                        logger.debug("Skipping dir or file %s" % entry)
                        continue
                    if os.path.isdir(entry):
                        logger.info("Remove %s" % entry)
                        if options.dry_run is False:
                            shutil.rmtree(entry)
                    else:
                        logger.info("Delete %s" % entry)
                        if options.dry_run is False:
                            os.unlink(entry)
            except OSError:
                logger.warning("Cannot access directory %s for purge,"
                               " ignoring." % datadir)
            fullpurge.append(commit.project_name)
            commit.flags |= FLAG_PURGED
            logger.info("Remove %s" % datadir)
            if options.dry_run is False:
                shutil.rmtree(datadir, ignore_errors=True)
        else:
            # If the commit was not successful, we need to be careful not to
            # remove the directory if there was a successful build
            if commit.status != "SUCCESS":
                othercommits = session.query(Commit).filter(
                    Commit.project_name == commit.project_name,
                    Commit.commit_hash == commit.commit_hash,
                    Commit.status == 'SUCCESS').count()

                if othercommits == 0:
                    logger.info("Remove %s" % datadir)
                    if options.dry_run is False:
                        shutil.rmtree(datadir, ignore_errors=True)
            else:
                logger.info("Remove %s" % datadir)
                if options.dry_run is False:
                    shutil.rmtree(datadir, ignore_errors=True)
            commit.flags |= FLAG_PURGED
    if options.dry_run is False:
        session.commit()
    closeSession(session)

    if cp.getboolean('DEFAULT', 'use_components'):
        purge_promoted_hashes(cp, mktime(timeparsed.timetuple()),
                              dry_run=options.dry_run)
