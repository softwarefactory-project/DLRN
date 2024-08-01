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

from distutils.util import strtobool
from typing import Optional

from pydantic import BaseModel
from pydantic import StrictStr
from pydantic import validator


class RepoStatusInput(BaseModel):
    """Input class that validates request's arguments for repo_status endpoint

    :param str commit_hash: A reference to the commit
    :param str distro_hash: A reference to the distro
    :param str extended_hash(optional): A reference to the extended commit
    :param bool success(optional): Only report successful/unsuccessful votes
    """
    commit_hash: StrictStr
    distro_hash: StrictStr
    extended_hash: Optional[StrictStr]
    success: Optional[bool]

    @validator('success')
    @classmethod
    def validate_boolean(cls, value):
        if value and not isinstance(value, bool):
            return bool(strtobool(value))
        return value
