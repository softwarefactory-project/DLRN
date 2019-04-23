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

# The LocalDriver provides the following:
#
# 1- A getpackages function based on finding all directories inside a specific
#    git repo, where each directory represents a package
#
# 2- A getinfo function based on a single-distgit repo paradigm

import logging
import os
import sh
import shutil

from dlrn.db import Commit
from dlrn.drivers.pkginfo import PkgInfoDriver
from rdopkg.utils import specfile

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("dlrn-local-driver")
logger.setLevel(logging.INFO)


class LocalDriver(PkgInfoDriver):
    DRIVER_CONFIG = {
        'local_driver': {
        }
    }

    def _get_version_from_pkg(self, packagepath):
        version = None
        for pkgfile in os.listdir(packagepath):
            if pkgfile.endswith('.spec'):
                spec = specfile.Spec(fn=os.path.join(packagepath, pkgfile))
                version = spec.get_tag('Version').encode()
        if not version:
            raise RuntimeError("No spec file or no version found")
        return version

    def getpackages(self, **kwargs):
        datadir = self.config_options.datadir
        is_cwd_distgit = [
            f for f in os.listdir(os.getcwd()) if f.endswith('.spec')]
        if not is_cwd_distgit:
            return []
        package = os.getcwd().split('/')[-1]
        src_dir = os.getcwd()
        if not os.path.isdir(os.path.join(src_dir, '.git')):
            raise RuntimeError("A git repository is expected")
        dest_dir = os.path.join(datadir, package)
        logger.info("Copy distgit source from %s to %s" % (src_dir, dest_dir))
        if not os.path.isdir(dest_dir):
            shutil.copytree(src_dir, dest_dir)
        pkg_hash = {}
        pkg_hash['name'] = package
        pkg_hash['maintainers'] = 'test@example.com'
        pkg_hash['master-distgit'] = dest_dir
        pkg_hash['upstream'] = 'Unknown'
        version = self._get_version_from_pkg(dest_dir).decode('utf-8')
        logger.info(
            "Got version %s for %s from the spec" % (version, package))
        pkg_hash['source-branch'] = version
        return [pkg_hash]

    def getinfo(self, **kwargs):
        project = kwargs.get('project')
        package = kwargs.get('package')
        datadir = self.config_options.datadir
        distro_dir = os.path.join(datadir, package['name'])

        # Get distro_hash from last commit in distgit directory
        git = sh.git.bake(_cwd=package['master-distgit'], _tty_out=False)
        repoinfo = str(git.log("--pretty=format:%H %ct", "-1", ".")
                       ).strip().split(" ")
        distro_hash = repoinfo[0]
        dt_distro = repoinfo[1]

        project_toprocess = []
        commit_hash = "%s-%s" % (project, package['source-branch'])
        commit = Commit(
            dt_commit=0, project_name=project,
            commit_hash=commit_hash, repo_dir=None,
            distro_hash=distro_hash, dt_distro=dt_distro,
            distgit_dir=distro_dir,
            commit_branch=package['source-branch'],
            dt_extended=0, extended_hash=None)
        project_toprocess.append(commit)

        return project_toprocess

    def preprocess(self, **kwargs):
        pass
