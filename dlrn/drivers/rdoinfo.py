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

from dlrn.drivers.pkginfodriver import PkgInfoDriver

from rdopkg.actionmods import rdoinfo
import rdopkg.utils.log

rdopkg.utils.log.set_colors('no')


class RdoInfoDriver(PkgInfoDriver):

    def __init__(self, *args, **kwargs):
        super(RdoInfoDriver, self).__init__(*args, **kwargs)

    def getpackages(self, **kwargs):
        """ Valid parameters:
        :param local_info_repo: local rdoinfo repo to use instead of fetching
                                the default one using rdopkg.
        :param tags: OpenStack release tags to use (mitaka, newton, etc).
        """
        local_info_repo = kwargs.get('local_info_repo')
        tags = kwargs.get('tags')
        inforepo = None

        if local_info_repo:
            inforepo = rdoinfo.RdoinfoRepo(local_repo_path=local_info_repo,
                                           apply_tag=tags)
        else:
            inforepo = rdoinfo.get_default_inforepo(apply_tag=tags)
            # rdopkg will clone/pull rdoinfo repo as needed (~/.rdopkg/rdoinfo)
            inforepo.init()
        pkginfo = inforepo.get_info()
        self.packages = pkginfo["packages"]
        if tags:
            # FIXME allow list of tags?
            self.packages = rdoinfo.filter_pkgs(self.packages, {'tags': tags})
        return self.packages
