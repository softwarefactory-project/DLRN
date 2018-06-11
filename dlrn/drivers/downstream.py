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


from dlrn.db import Commit
from dlrn.drivers.pkginfo import PkgInfoDriver
from dlrn.repositories import getdistrobranch
from dlrn.repositories import getsourcebranch
from dlrn.repositories import refreshrepo

import csv
import logging
import os
import sh

from distroinfo import info
from six.moves.urllib.request import urlopen


logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("dlrn-downstream-driver")
logger.setLevel(logging.INFO)
rdoinfo_repo = ('https://raw.githubusercontent.com/'
                'redhat-openstack/rdoinfo/master/')


class DownstreamInfoDriver(PkgInfoDriver):

    def __init__(self, *args, **kwargs):
        super(DownstreamInfoDriver, self).__init__(*args, **kwargs)

    def getpackages(self, **kwargs):
        """Valid parameters:

        :param local_info_repo: local rdoinfo repo to use instead of fetching
                                the default one using distroinfo.
        :param tags: release tags to use (mitaka, newton, etc).
        """
        local_info_repo = kwargs.get('local_info_repo')
        tags = kwargs.get('tags')
        inforepo = None

        if local_info_repo:
            inforepo = info.DistroInfo(
                info_files='rdo.yml',
                local_info=local_info_repo)
        elif self.config_options.rdoinfo_repo:
            inforepo = info.DistroInfo(
                info_files='rdo.yml',
                remote_git_info=self.config_options.rdoinfo_repo)
        else:
            # distroinfo will fetch info files from the rdoinfo repo as needed
            # and store them under ~/.distroinfo/cache
            inforepo = info.DistroInfo(
                info_files='rdo.yml',
                remote_info=rdoinfo_repo)

        pkginfo = inforepo.get_info(apply_tag=tags)

        self.packages = pkginfo["packages"]
        if tags:
            # FIXME allow list of tags?
            self.packages = rdoinfo.filter_pkgs(self.packages, {'tags': tags})
        return self.packages

    def getversions(self):
        """Fetch 'versions.csv'

        from versions_url config option and return the contained data as
        a dict with package name as a key.
        """
        versions_url = self.config_options.versions_url
        if not versions_url:
            raise Exception(
                "Missing required versions_url config option"
                "for dlrn.drivers.downstream driver.")

        # return versions.csv as a dict with package name as a key
        vers = {}
        r = urlopen(versions_url)
        content = list(map(lambda x: x.decode('utf8'), r.readlines()))
        # first line is headers
        for row in csv.reader(content[1:]):
            vers[row[0]] = row[1:]
        return vers

    def getinfo(self, **kwargs):
        project = kwargs.get('project')
        package = kwargs.get('package')
        local = kwargs.get('local')
        dev_mode = kwargs.get('dev_mode')
        datadir = self.config_options.datadir
        repo = package['upstream']
        distro = package['master-distgit']

        distro_dir = self._distgit_clone_dir(package['name'])
        distro_dir_full = self.distgit_dir(package['name'])
        distro_branch = getdistrobranch(package)
        source_branch = getsourcebranch(package)
        versions = self.getversions()

        # only process packages present in versions.csv
        if package['name'] not in versions:
            logger.warning('Package %s not present in %s - skipping.' % (
                package['name'], self.config_options.versions_url))
            return []

        if dev_mode is False:
            try:
                distro_branch, _, dt_distro = refreshrepo(
                    distro, distro_dir, distro_branch, local=local,
                    full_path=distro_dir_full)
                # extract distro_hash from versions.csv
                distro_hash = versions[package['name']][1]
            except Exception:
                # The error was already logged by refreshrepo, and we want
                # to avoid halting the whole run because this distgit repo
                # failed, so return an empty list
                return []
        else:
            distro_hash = "dev"
            dt_distro = 0  # Doesn't get used in dev mode
            if not os.path.isdir(distro_dir):
                # We should fail in this case, since we are running
                # in dev mode, so no try/except
                refreshrepo(distro, distro_dir, distro_branch, local=local,
                            full_path=distro_dir_full)

        # repo is usually a string, but if it contains more then one entry we
        # git clone into a project subdirectory
        repos = [repo]
        if isinstance(repo, list):
            repos = repo
        project_toprocess = []
        for repo in repos:
            repo_dir = os.path.join(datadir, project)
            if len(repos) > 1:
                repo_dir = os.path.join(repo_dir, os.path.split(repo)[1])
            try:
                source_branch, _, _ = refreshrepo(repo, repo_dir,
                                                  source_branch,
                                                  local=local)
            except Exception:
                # The error was already logged by refreshrepo, and the only
                # side-effect is that we are not adding this commit to the
                # list of commits to be processed, so we can ignore it and
                # move on to the next repo
                continue

            dt = 0
            commit_hash = versions[package['name']][1]
            commit = Commit(dt_commit=float(dt), project_name=project,
                            commit_hash=commit_hash, repo_dir=repo_dir,
                            distro_hash=distro_hash, dt_distro=dt_distro,
                            extended_hash=None, dt_extended=0,
                            distgit_dir=self.distgit_dir(package['name']),
                            commit_branch=source_branch)
            project_toprocess.append(commit)
        return project_toprocess

    def preprocess(self, **kwargs):
        # Pre-processing is only required if we have a jinja2 spec template
        package_name = kwargs.get('package_name')
        distgit_dir = self.distgit_dir(package_name)
        # Now, try to check if we need to run a pre-processing job
        preprocess_needed = False
        for f in os.listdir(distgit_dir):
            if f.endswith('.spec.j2'):
                # We have a template here, so we have to preprocess
                preprocess_needed = True
                break
        if preprocess_needed:
            logger.info('Pre-processing template at %s' % distgit_dir)
            renderspec = sh.renderspec.bake(_cwd=distgit_dir,
                                            _tty_out=False, _timeout=3600)
            renderspec('--spec-style', 'fedora', '--epoch',
                       '../../epoch/fedora.yaml')
        return

    def distgit_dir(self, package_name):
        datadir = self.config_options.datadir
        # Find extra directory inside it, if needed
        extra_dir = '/'
        for package in self.packages:
            if package['name'] == package_name:
                if 'distgit-path' in package:
                    extra_dir = package['distgit-path']
                    break
        return os.path.join(datadir, package_name + "_distro",
                            extra_dir.lstrip('/'))

    def _distgit_clone_dir(self, package_name):
        datadir = self.config_options.datadir
        return os.path.join(datadir, package_name + "_distro")
