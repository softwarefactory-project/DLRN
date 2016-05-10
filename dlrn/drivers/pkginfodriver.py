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

# PkgInfoDriver derived classes only need to expose one function:
# getpackages(). This function will return an array of hashes. Each individual
# hash must contain the following mandatory parameters (others are optional):
# - 'name' : package name
# - 'upstream': URL for upstream repo
# - 'master-distgit': URL for distgit repo
# - 'maintainers': list of e-mail addresses for package maintainers


class PkgInfoDriver(object):
    def __init__(self, *args, **kwargs):
        self.packages = []

    def getpackages(self):
        return self.packages
