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

        global _config_options
        _config_options = self


def getConfigOptions():
    return _config_options
