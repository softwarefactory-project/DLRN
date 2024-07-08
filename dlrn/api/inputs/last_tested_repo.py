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

from pydantic import BaseModel
from pydantic import root_validator
from pydantic import StrictStr
from pydantic import validator
from typing import Optional

from dlrn.api.utils import InvalidUsage


class LastTestedRepoInput(BaseModel):
    """Input class that validates request's arguments for last_tested_repo

    :param str max_age: Maximum age in hours, used as base for the search
    :param bool success(optional): Only report successful/unsuccessful votes
    :param str job_id(optional): Name of the CI that sent the vote
    :param bool sequential_mode(optional): If set to true, change the search
                                          algorithm to only use
                                          previous_job_id as CI name to
                                          search for. Defaults to false
    :param str previous_job_id(optional): CI name to search for,
                                          if sequential_mode is True
    :param str component(optional): Only get votes for this component

    """
    max_age: int
    success: Optional[bool]
    job_id: Optional[StrictStr]
    sequential_mode: Optional[bool]
    previous_job_id: Optional[StrictStr] = None
    component: Optional[StrictStr]

    @validator('max_age')
    @classmethod
    def validate_max_age(cls, max_age):
        if int(max_age) < 0:
            raise InvalidUsage('Max age parameter must be greater than or '
                               'equal to 0', status_code=400)
        return int(max_age)

    @root_validator
    def validate_previous_with_sequential(cls, values):
        if (values.get('sequential_mode') and
                values.get('previous_job_id') is None):
            raise InvalidUsage('Missing parameter previous_job_id',
                               status_code=400)
        return values
