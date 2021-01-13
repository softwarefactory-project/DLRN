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
import sys

from contextlib import closing
from six.moves import configparser
from six.moves import urllib
from six.moves.urllib.request import urlopen
from tempfile import mkstemp

from dlrn.config import ConfigOptions
from dlrn.config import setup_logging
from dlrn.db import closeSession
from dlrn.db import getLastProcessedCommit
from dlrn.db import getSession
from dlrn.shell import post_build
from dlrn.shell import process_build_result
from dlrn.utils import import_object
from dlrn.utils import loadYAML_list
from dlrn.utils import lock_file


logger = logging.getLogger("dlrn-remote")


def import_commit(repo_url, config_file, db_connection=None,
                  local_info_repo=None):
    cp = configparser.RawConfigParser()
    cp.read(config_file)
    config_options = ConfigOptions(cp)
    pkginfo_driver = config_options.pkginfo_driver
    pkginfo = import_object(pkginfo_driver, cfg_options=config_options)
    packages = pkginfo.getpackages(local_info_repo=local_info_repo,
                                   tags=config_options.tags,
                                   dev_mode=False)

    remote_yaml = repo_url + '/' + 'commit.yaml'
    with closing(urlopen(remote_yaml)) as r:
        contents = map(lambda x: x.decode('utf8'), r.readlines())

    osfd, tmpfilename = mkstemp()
    with os.fdopen(osfd, 'w') as fp:
        fp.writelines(contents)

    commits = loadYAML_list(tmpfilename)
    os.remove(tmpfilename)
    datadir = os.path.realpath(config_options.datadir)
    if not os.path.exists(datadir):
        os.makedirs(datadir)

    for commit in commits:
        commit.id = None
        if commit.artifacts == 'None':
            commit.artifacts = None
        commit.dt_build = int(commit.dt_build)
        commit.dt_commit = float(commit.dt_commit)
        commit.dt_distro = int(commit.dt_distro)
        # Check if the latest built commit for this project is newer
        # than this one. In that case, we should ignore it
        if db_connection:
            session = getSession(db_connection)
        else:
            session = getSession(config_options.database_connection)
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
                with closing(urlopen(logfile_url)) as r:
                    contents = map(lambda x: x.decode('utf8'), r.readlines())
                with open(os.path.join(yumrepodir, logfile), "w") as fp:
                    fp.writelines(contents)
            except urllib.error.HTTPError:
                # Ignore errors, if the remote build failed there may be
                # some missing files
                pass

        if commit.artifacts:
            for rpm in commit.artifacts.split(","):
                rpm_url = repo_url + '/' + rpm.split('/')[-1]
                try:
                    with closing(urlopen(rpm_url)) as r:
                        contents = r.read()
                    with open(os.path.join(datadir, rpm), "wb") as fp:
                        fp.write(contents)
                except urllib.error.HTTPError:
                    if rpm != 'None':
                        logger.warning("Failed to download rpm file %s"
                                       % rpm_url)
        # Get remote update lock, to prevent any other remote operation
        # while we are creating the repo and updating the database
        logger.debug("Acquiring remote update lock")
        with lock_file(os.path.join(datadir, 'remote.lck')):
            logger.debug("Acquired lock")
            if commit.status == 'SUCCESS':
                built_rpms = []
                for rpm in commit.artifacts.split(","):
                    built_rpms.append(rpm)
                status = [commit, built_rpms, commit.notes, None]
                post_build(status, packages, session)
            else:
                pkg = [p for p in packages if p['name'] == package][0]
                # Here we fire a refresh of the repositories
                # (upstream and distgit) to be sure to have them in the
                # data directory. We need that in the case the worker
                # is running on another host mainly for the
                # submit_review.sh script.
                pkginfo.getinfo(project=pkg["name"], package=pkg,
                                since='-1', local=False, dev_mode=False)
                # Paths on the worker might differ so we overwrite them
                # to reflect data path on the local API host.
                commit.distgit_dir = pkginfo.distgit_dir(pkg['name'])
                commit.repo_dir = os.path.join(
                    config_options.datadir, pkg['name'])
                status = [commit, '', '', commit.notes]
            process_build_result(status, packages, session, [])
            closeSession(session)   # Keep one session per commit
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
    parser.add_argument('--debug', action='store_true',
                        help="Print debug logs")

    options = parser.parse_args(sys.argv[1:])

    setup_logging(options.debug)

    return import_commit(options.repo_url, options.config_file,
                         local_info_repo=options.info_repo)
