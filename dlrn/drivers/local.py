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

    def _get_infos_from_pkg(self, packagepath):
        version = None
        package = None
        if not os.path.isdir(os.path.join(packagepath, '.git')):
            raise RuntimeError(
                'The distgit directory must a be git repository')
        for pkgfile in os.listdir(packagepath):
            if pkgfile.endswith('.spec'):
                spec = specfile.Spec(fn=os.path.join(packagepath, pkgfile))
                version = spec.get_tag('Version')
                package = pkgfile.replace('.spec', '')
        if not version:
            raise RuntimeError("No spec file or no version found")
        return package, version

    def getpackages(self, **kwargs):
        datadir = self.config_options.datadir
        # src_dir is only set for the test case. Normal behavior is
        # to look at the current directory.
        if 'src_dir' in kwargs:
            src_dir = kwargs['src_dir']
        else:
            src_dir = os.getcwd()
        is_src_dir_distgit = [
            f for f in os.listdir(src_dir) if f.endswith('.spec')]
        if not is_src_dir_distgit:
            return []
        package, version = self._get_infos_from_pkg(src_dir)
        dest_dir = os.path.join(datadir, package)
        logger.info("Copy distgit source from %s to %s" % (src_dir, dest_dir))
        if os.path.isdir(dest_dir):
            shutil.rmtree(dest_dir)
        shutil.copytree(src_dir, dest_dir)
        pkg_hash = {}
        pkg_hash['name'] = package
        pkg_hash['maintainers'] = 'test@example.com'
        pkg_hash['master-distgit'] = dest_dir
        pkg_hash['upstream'] = 'Unknown'
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
            type='rpm',
            commit_hash=commit_hash, repo_dir=None,
            distro_hash=distro_hash, dt_distro=dt_distro,
            distgit_dir=distro_dir,
            commit_branch=package['source-branch'],
            dt_extended=0, extended_hash=None, component=None)
        project_toprocess.append(commit)

        return PkgInfoDriver.Info(project_toprocess, False)

    def preprocess(self, **kwargs):
        pass
