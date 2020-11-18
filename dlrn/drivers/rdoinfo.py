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

# The RdoInfoDriver provides the following:
#
# 1- A getpackages function based on output provided by rdoinfo
#    (https://github.com/redhat-openstack/rdoinfo)
#
# 2- A getinfo function based on a multi-distgit repo paradigm
#
# 3- A preprocess function that is only used if the distgit directory
#    containts a .spec.j2 file

from dlrn.db import Commit
from dlrn.drivers.pkginfo import PkgInfoDriver
from dlrn.repositories import getdistrobranch
from dlrn.repositories import getsourcebranch
from dlrn.repositories import refreshrepo
from dlrn.utils import run_external_preprocess

import logging
import os
import sh

from distroinfo import query
from distroinfo import info


logger = logging.getLogger("dlrn-rdoinfo-driver")
rdoinfo_repo = ('https://raw.githubusercontent.com/'
                'redhat-openstack/rdoinfo/master/')

def buildtagsonly(package):
    return ('tags' in package and package['tags'] is not None and
            'build-tags-only' in package['tags'] or
            'build-tags-only' in package)


class RdoInfoDriver(PkgInfoDriver):
    DRIVER_CONFIG = {
        'rdoinfo_driver': {
            'rdoinfo_repo': {'name': 'repo'},
            'rdoinfo_file': {'name': 'info_files', 'type': 'list',
                             'default': ['rdo.yml']},
            'cache_dir': {},
        }
    }

    def __init__(self, *args, **kwargs):
        super(RdoInfoDriver, self).__init__(*args, **kwargs)
        self.distroinfo_path = None

    def getpackages(self, **kwargs):
        """ Valid parameters:
        :param local_info_repo: local rdoinfo repo to use instead of fetching
                                the default one using rdopkg.
        :param tags: OpenStack release tags to use (mitaka, newton, etc).
        """
        local_info_repo = kwargs.get('local_info_repo')
        tags = kwargs.get('tags')
        inforepo = None
        info_files = self.config_options.rdoinfo_file

        if local_info_repo:
            inforepo = info.DistroInfo(
                info_files=self.config_options.rdoinfo_file,
                local_info=local_info_repo,
                cache_base_path=self.config_options.cache_dir)
            # NOTE(jpena): in general, info_files will only contain one file,
            # but it supports multiple... In that case, we will have a comma
            # separated list of URLs
            self.distroinfo_path = "%s/%s" % (local_info_repo.rstrip('/'),
                                              info_files[0])
            for extra_file in info_files[1:]:
                self.distroinfo_path += ",%s/%s" % (
                    local_info_repo.rstrip('/'))
        elif self.config_options.rdoinfo_repo:
            inforepo = info.DistroInfo(
                info_files=self.config_options.rdoinfo_file,
                remote_git_info=self.config_options.rdoinfo_repo,
                cache_base_path=self.config_options.cache_dir)
            self.distroinfo_path = "%s/%s" % (
                self.config_options.rdoinfo_repo.rstrip('/'), info_files[0])
            for extra_file in info_files[1:]:
                self.distroinfo_path += ",%s/%s" % (
                    self.config_options.rdoinfo_repo.rstrip('/'))
        else:
            # distroinfo will fetch info files from the rdoinfo repo as needed
            # and store them under ~/.distroinfo/cache
            inforepo = info.DistroInfo(
                info_files=self.config_options.rdoinfo_file,
                remote_info=rdoinfo_repo,
                cache_base_path=self.config_options.cache_dir)
            self.distroinfo_path = "%s/%s" % (rdoinfo_repo.rstrip('/'),
                                              info_files[0])
            for extra_file in info_files[1:]:
                self.distroinfo_path += ",%s/%s" % (
                    rdoinfo_repo.rstrip('/'))

        pkginfo = inforepo.get_info(apply_tag=tags)

        self.packages = pkginfo["packages"]
        if tags:
            # FIXME allow list of tags?
            self.packages = query.filter_pkgs(self.packages, {'tags': tags})
        return self.packages

    def getinfo(self, **kwargs):
        project = kwargs.get('project')
        package = kwargs.get('package')
        since = kwargs.get('since')
        local = kwargs.get('local')
        dev_mode = kwargs.get('dev_mode')
        datadir = self.config_options.datadir
        repo = package['upstream']
        distro = package['master-distgit']
        tags_only = buildtagsonly(package)

        distro_dir = self._distgit_clone_dir(package['name'])
        distro_dir_full = self.distgit_dir(package['name'])
        distro_branch = getdistrobranch(package)
        source_branch = getsourcebranch(package)

        if dev_mode is False:
            try:
                distro_branch, distro_hash, dt_distro = refreshrepo(
                    distro, distro_dir, distro_branch, local=local,
                    full_path=distro_dir_full)
            except Exception:
                # The error was already logged by refreshrepo, and we want
                # to avoid halting the whole run because this distgit repo
                # failed, so return an empty list
                return PkgInfoDriver.Info([], True)
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
                source_branch, _, _ = refreshrepo(repo, repo_dir, source_branch,
                                                  local=local)
            except Exception:
                # The error was already logged by refreshrepo, and the only
                # side-effect is that we are not adding this commit to the
                # list of commits to be processed, so we can ignore it and
                # move on to the next repo
                return PkgInfoDriver.Info([], True)

            git = sh.git.bake(_cwd=repo_dir, _tty_out=False)
            # Git gives us commits already sorted in the right order
            if tags_only is True:
                logger.info('Building tags only for %s' % project)
                if since == '-1':
                    # we need 2 entries as HEAD will be listed too
                    since = '-2'
                lines = filter(
                    lambda x: x.find('tag: ') >= 0,
                    git.log('--simplify-by-decoration',
                            "--pretty=format:'%ct %H %d'",
                            since, "--first-parent",
                            "--reverse", "%s" % source_branch))
            else:
                lines = git.log("--pretty=format:'%ct %H'",
                                since, "--first-parent",
                                "--reverse")

            for line in lines:
                dt, commit_hash = str(line).strip().strip("'").split(" ")[:2]
                if self.config_options.use_components and 'component' in package:
                    component = package['component']
                else:
                    component = None
                commit = Commit(dt_commit=float(dt), project_name=project,
                                type="rpm",
                                commit_hash=commit_hash, repo_dir=repo_dir,
                                distro_hash=distro_hash, dt_distro=dt_distro,
                                distgit_dir=self.distgit_dir(package['name']),
                                commit_branch=source_branch,
                                dt_extended=0, extended_hash=None,
                                component=component)
                project_toprocess.append(commit)

        return PkgInfoDriver.Info(project_toprocess, False)

    def preprocess(self, **kwargs):
        # Pre-processing is only required if we have a jinja2 spec template
        package_name = kwargs.get('package_name')
        commit_hash = kwargs.get('commit_hash')
        distgit_dir = self.distgit_dir(package_name)
        source_dir = "%s/%s" % (self.config_options.datadir, package_name)
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

        for custom_preprocess in self.config_options.custom_preprocess:
            if custom_preprocess != '':
                run_external_preprocess(
                    cmdline=custom_preprocess,
                    pkgname=package_name,
                    distgit=distgit_dir,
                    distroinfo=self.distroinfo_path,
                    source_dir=source_dir,
                    commit_hash=commit_hash)
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
