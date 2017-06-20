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
import fcntl
import logging
import os
import sys
import urllib2

from six.moves import configparser
from tempfile import mkstemp

from dlrn.config import ConfigOptions
from dlrn.db import getLastProcessedCommit
from dlrn.db import getSession
from dlrn.shell import default_options
from dlrn.shell import post_build
from dlrn.shell import process_build_result
from dlrn.utils import import_object
from dlrn.utils import loadYAML_list

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("dlrn-remote")
logger.setLevel(logging.INFO)


def import_commit(repo_url, config_file, db_connection=None,
                  local_info_repo=None):
    cp = configparser.RawConfigParser(default_options)
    cp.read(config_file)
    config_options = ConfigOptions(cp)
    pkginfo_driver = config_options.pkginfo_driver
    pkginfo = import_object(pkginfo_driver, cfg_options=config_options)
    packages = pkginfo.getpackages(local_info_repo=local_info_repo,
                                   tags=config_options.tags,
                                   dev_mode=False)
    if db_connection:
        session = getSession(db_connection)
    else:
        session = getSession(config_options.database_connection)

    remote_yaml = repo_url + '/' + 'commit.yaml'
    r = urllib2.urlopen(remote_yaml)
    contents = r.readlines()
    osfd, tmpfilename = mkstemp()
    fp = os.fdopen(osfd, 'w')
    fp.writelines(contents)
    fp.close()

    commits = loadYAML_list(tmpfilename)
    os.remove(tmpfilename)
    datadir = os.path.realpath(config_options.datadir)
    if not os.path.exists(datadir):
        os.makedirs(datadir)

    with open(os.path.join(datadir, 'remote.lck'), 'a') as lock_fp:
        for commit in commits:
            commit.id = None
            if commit.rpms == 'None':
                commit.rpms = None
            commit.dt_build = int(commit.dt_build)
            commit.dt_commit = float(commit.dt_commit)
            commit.dt_distro = int(commit.dt_distro)
            # Check if the latest built commit for this project is newer
            # than this one. In that case, we should ignore it
            package = commit.project_name
            old_commit = getLastProcessedCommit(session, package)
            if old_commit:
                if old_commit.dt_commit >= commit.dt_commit:
                    if old_commit.dt_distro >= commit.dt_distro:
                        logger.info('Skipping commit %s, a newer commit is '
                                    'already built\n'
                                    'Old: %s %s, new: %s %s' %
                                    (commit.commit_hash, old_commit.dt_commit,
                                     old_commit.dt_distro, commit.dt_commit,
                                     commit.dt_distro))
                        continue    # Skip

            yumrepodir = os.path.join(datadir, "repos",
                                      commit.getshardedcommitdir())
            if not os.path.exists(yumrepodir):
                os.makedirs(yumrepodir)

            for logfile in ['build.log', 'installed', 'mock.log', 'root.log',
                            'rpmbuild.log', 'state.log']:
                logfile_url = repo_url + '/' + logfile
                try:
                    r = urllib2.urlopen(logfile_url)
                    contents = r.readlines()
                    with open(os.path.join(yumrepodir, logfile), "w") as fp:
                        fp.writelines(contents)
                except urllib2.HTTPError:
                    # Ignore errors, if the remote build failed there may be
                    # some missing files
                    pass

            if commit.rpms:
                for rpm in commit.rpms.split(","):
                    rpm_url = repo_url + '/' + rpm.split('/')[-1]
                    try:
                        r = urllib2.urlopen(rpm_url)
                        contents = r.readlines()
                        with open(os.path.join(datadir, rpm), "w") as fp:
                            fp.writelines(contents)
                    except urllib2.HTTPError:
                        if rpm != 'None':
                            logger.warning("Failed to download rpm file %s"
                                           % rpm_url)
            # Get remote update lock, to prevent any other remote operation
            # while we are creating the repo and updating the database
            logger.debug("Acquiring remote update lock")
            fcntl.flock(lock_fp, fcntl.LOCK_EX)
            logger.debug("Acquired lock")
            if commit.status == 'SUCCESS':
                built_rpms = []
                for rpm in commit.rpms.split(","):
                    built_rpms.append(rpm)
                status = [commit, built_rpms, commit.notes, None]
                post_build(status, packages, session)
            else:
                status = [commit, '', '', commit.notes]
            process_build_result(status, packages, session, [])
            fcntl.flock(lock_fp, fcntl.LOCK_UN)
            logger.debug("Released lock")
    return 0


def remote():
    parser = argparse.ArgumentParser()
    # Some of the non-positional arguments are required, so change the text
    # saying "optional arguments" to just "arguments":
    parser._optionals.title = 'arguments'

    parser.add_argument('--config-file',
                        default='projects.ini',
                        help="Config file. Default: projects.ini")
    parser.add_argument('--repo-url',
                        help="Base repository URL for remotely generated repo "
                             "(required)", required=True)
    parser.add_argument('--info-repo',
                        help="use a local rdoinfo repo instead of "
                             "fetching the default one using rdopkg. Only "
                             "applies when pkginfo_driver is rdoinfo in "
                             "projects.ini")

    options, args = parser.parse_known_args(sys.argv[1:])

    return import_commit(options.repo_url, options.config_file,
                         local_info_repo=options.info_repo)
