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
"""
SRPMDriver derived classes expose the following methods to customize
the preparation of .src.rpm used to build packages:

prepare_srpm(). This method will prepare .src.rpm source package using
                the driver-specific approach.
"""


class SRPMDriver(object):
    def __init__(self, *args, **kwargs):
        self.config_options = kwargs.get('cfg_options')

    def prepare_srpm(self):
        return False
