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

# The CPaaSInfoDriver provides the following:
#
# 1- A getpackages function based on output provided by a project.yaml file
#    (link TBD)
#
# 2- A getinfo function TBD
#
# 3- A preprocess function that honors the custom preprocess option

import logging
import os
import sh
import yaml

from dlrn.db import Commit
from dlrn.repositories import getdistrobranch
from dlrn.repositories import getsourcebranch
from dlrn.repositories import refreshrepo
from dlrn.utils import run_external_preprocess
from six.moves.urllib.request import urlopen

logger = logging.getLogger("dlrn-cpaas-driver")


class CPaaSInfoDriver(PkgInfoDriver):
    DRIVER_CONFIG = {
        'cpaas_driver': {
            'definition_url': {},
        }
    }

    def __init__(self, *args, **kwargs):
        super(CPaaSInfoDriver, self).__init__(*args, **kwargs)

    def getpackages(self, **kwargs):
        r = urlopen(self.config_options.definition_url)
        data = yaml.safe_load(r)

        packages = []
        for project in data['product']['projects']:
            project_owner = project.get('owner', None)
            for component in project['components']:
                pkg_hash = {}
                pkg_hash['name'] = component['name']
                if component['type'] == 'rpms':
                    pkg_hash['type'] = 'rpm'
                elif component['type'] == 'containers':
                    pkg_hash['type'] = 'container'
                else:
                    continue
                pkg_hash['maintainers'] = component.get('owner', project_owner)
                pkg_hash['distro-branch'] = component['build'][0]['brew-tag']
                packages.append(pkg_hash)

                # FIXME(jpena): we are still missing some important information
                # pkg_hash['master-distgit'] =
                # pkg_hash['upstream'] =
                # pkg_hash['source-branch'] =

        return packages

    def getinfo(self, **kwargs):
        project = kwargs.get('project')
        package = kwargs.get('package')
        since = kwargs.get('since')
        local = kwargs.get('local')
        dev_mode = kwargs.get('dev_mode')
        repo = package['upstream']
        datadir = self.config_options.datadir

        distro_dir = self._distgit_dir(package['name'])
        distro_branch = getdistrobranch(package)
        source_branch = getsourcebranch(package)

        if dev_mode is False:
            try:
                distro_branch, distro_hash, dt_distro = refreshrepo(
                    distro, distro_dir, distro_branch, local=local)
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
                refreshrepo(distro, distro_dir, distro_branch, local=local)

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
                                                  source_branch, local=local)
            except Exception:
                # The error was already logged by refreshrepo, and the only
                # side-effect is that we are not adding this commit to the
                # list of commits to be processed, so we can ignore it and
                # move on to the next repo
                continue

            git = sh.git.bake(_cwd=repo_dir, _tty_out=False)
            # Git gives us commits already sorted in the right order
            lines = git.log("--pretty=format:'%ct %H'", since,
                            "--first-parent", "--reverse")

            for line in lines:
                dt, commit_hash = str(line).strip().strip("'").split(" ")
                commit = Commit(dt_commit=float(dt), project_name=project,
                                type='rpm',
                                commit_hash=commit_hash, repo_dir=repo_dir,
                                distro_hash=distro_hash, dt_distro=dt_distro,
                                distgit_dir=distro_dir,
                                commit_branch=source_branch,
                                dt_extended=0, extended_hash=None)
                project_toprocess.append(commit)

        return project_toprocess

    def preprocess(self, **kwargs):
        # Pre-processing is only required if we have a jinja2 spec template
        package_name = kwargs.get('package_name')
        commit_hash = kwargs.get('commit_hash')
        distgit_dir = self._distgit_dir(package_name)
        source_dir = "%s/%s" % (self.config_options.datadir, package_name)

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

    def _distgit_dir(self, package_name):
        datadir = self.config_options.datadir
        return os.path.join(datadir, package_name + "_distro")
