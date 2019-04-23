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
#
# 3- A preprocess function using renderspec on any *.spec.j2 file found in the
#    distgit.

import logging
import os
import re
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

    def __init__(self, *args, **kwargs):
        super(LocalDriver, self).__init__(*args, **kwargs)

    def _get_version_from_pkg(self, packagepath):
        for pkgfile in os.listdir(packagepath):
            if pkgfile.endswith('.spec'):
                spec = specfile.Spec(fn=os.path.join(packagepath, pkgfile))
                version = spec.get_tag('Version').encode()
        return version

    def getpackages(self, **kwargs):
        datadir = self.config_options.datadir
        is_cwd_distgit = [
            f for f in os.listdir(os.getcwd()) if f.endswith('.spec')]
        if not is_cwd_distgit:
            return []
        package = os.getcwd().split('/')[-1]
        src_dir = os.getcwd()
        dest_dir = os.path.join(datadir, package)
        logger.info("Copy distgit source from %s to %s" % (src_dir, dest_dir))
        if not os.path.isdir(dest_dir):
            shutil.copytree(src_dir, dest_dir)
        pkg_hash = {}
        pkg_hash['name'] = package
        pkg_hash['maintainers'] = 'test@example.com'
        pkg_hash['master-distgit'] = dest_dir
        pkg_hash['upstream'] = 'Unknown'
        version = self._get_version_from_pkg(dest_dir)
        logger.info(
            "Got version %s for %s from the spec" % (version, package))
        pkg_hash['source-branch'] = version
        return [pkg_hash]

    def getinfo(self, **kwargs):
        project = kwargs.get('project')
        package = kwargs.get('package')
        datadir = self.config_options.datadir
        distro_dir = os.path.join(datadir, package['name'])

        project_toprocess = []
        commit = Commit(
            dt_commit=0, project_name=project,
            commit_hash='0' * 64, repo_dir=None,
            distro_hash='0' * 64, dt_distro=0,
            distgit_dir=distro_dir,
            commit_branch=None,
            dt_extended=0, extended_hash=None)
        project_toprocess.append(commit)

        return project_toprocess

    def preprocess(self, **kwargs):
        pass
