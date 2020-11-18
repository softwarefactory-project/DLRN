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

# PkgInfoDriver derived classes expose the following functions:
#
# getpackages(). This function will return an array of hashes. Each individual
# hash must contain the following mandatory parameters (others are optional):
# - 'name' : package name
# - 'upstream': URL for upstream repo
# - 'master-distgit': URL for distgit repo
# - 'maintainers': list of e-mail addresses for package maintainers
#
# getinfo(). This function will return a list of commits to be processed for a
#            specific package, and True if the package was skipped due to any
#            git clone error, False if not.
#
# preprocess(). This function will run any required pre-processing for the spec
#               files.
#
# distgit_dir(). This function will return the distgit repo directory for a
#                given package name.

from collections import namedtuple


class PkgInfoDriver(object):
    Info = namedtuple('Info', ['commits', 'skipped'])

    def __init__(self, *args, **kwargs):
        self.packages = []
        self.config_options = kwargs.get('cfg_options')

    def getpackages(self):
        return self.packages

    def getinfo(self):
        return Info(None, False)

    def preprocess(self):
        return

    def distgit_dir(self, package_name):
        return ''
