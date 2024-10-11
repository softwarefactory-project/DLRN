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

from pydantic import AnyHttpUrl
from pydantic import BaseModel


class RemoteImportInput(BaseModel):
    """Input class that validates request's arguments for remote_import

    :param str repo_url: Other DLRN instance repo with hash
                         to import from by using HTTP or HTTPS
                         protocols. For example https://$instance_FQDN/\
                         $builder/$repo/$component/cd/88/cd88...
    """
    repo_url: AnyHttpUrl
