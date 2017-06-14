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

_config_options = None


class ConfigOptions(object):

    def __init__(self, cp):
        self.tags = cp.get('DEFAULT', 'tags')
        self.datadir = cp.get('DEFAULT', 'datadir')
        self.gerrit = cp.get('DEFAULT', 'gerrit')
        self.maxretries = cp.getint('DEFAULT', 'maxretries')
        self.baseurl = cp.get('DEFAULT', 'baseurl')
        self.smtpserver = cp.get('DEFAULT', 'smtpserver')
        self.distro = cp.get('DEFAULT', 'distro')
        self.source = cp.get('DEFAULT', 'source')
        self.target = cp.get('DEFAULT', 'target')
        self.reponame = cp.get('DEFAULT', 'reponame')
        self.rsyncdest = cp.get('DEFAULT', 'rsyncdest')
        self.rsyncport = cp.get('DEFAULT', 'rsyncport')
        self.scriptsdir = cp.get('DEFAULT', 'scriptsdir')
        self.templatedir = cp.get('DEFAULT', 'templatedir')
        self.pkginfo_driver = cp.get('DEFAULT', 'pkginfo_driver')
        self.workers = cp.getint('DEFAULT', 'workers')
        self.gerrit_topic = cp.get('DEFAULT', 'gerrit_topic')
        self.database_connection = cp.get('DEFAULT', 'database_connection')
        self.fallback_to_master = cp.getboolean('DEFAULT',
                                                'fallback_to_master')

        # Handling for optional sections, driver-based
        if cp.has_section('gitrepo_driver'):
            if cp.has_option('gitrepo_driver', 'repo'):
                self.gitrepo_repo = cp.get('gitrepo_driver', 'repo')
            else:
                self.gitrepo_repo = None
            if cp.has_option('gitrepo_driver', 'directory'):
                self.gitrepo_dir = cp.get('gitrepo_driver', 'directory')
            else:
                self.gitrepo_dir = None
            if cp.has_option('gitrepo_driver', 'skip'):
                self.skip_dirs = cp.get('gitrepo_driver', 'skip').split(',')
            else:
                self.skip_dirs = None
            if cp.has_option('gitrepo_driver', 'use_version_from_spec'):
                use_spec = cp.getboolean('gitrepo_driver',
                                         'use_version_from_spec')
                self.use_version_from_spec = use_spec
            else:
                self.use_version_from_spec = False
        global _config_options
        _config_options = self


def getConfigOptions():
    return _config_options
