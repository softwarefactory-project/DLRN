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
from typing import Optional

from dlrn.api.utils import InvalidUsage


class ReportResultInput(BaseModel):
    """Input class that validates request's arguments for report result.

    Either commit_hash+distro_hash or aggregate_hash must be provided
    :param int timestamp: CI execution timestamp
    :param bool success: Result success boolean
    :param str job_id: Result job_id identifier
    :param str url: URL where more information can be found
    :param str commit_hash: Result commit hash identifier
    :param str distro_hash: Result distro hash identifier
    :param str extended_hash: Result extended hash identifier
    :param str aggregate_hash: Result aggregate hash identifier
    :param str notes: Return metrics for package_name
    """
    timestamp: int
    success: bool
    job_id: StrictStr
    url: str
    commit_hash: Optional[StrictStr]
    distro_hash: Optional[StrictStr]
    extended_hash: Optional[StrictStr]
    aggregate_hash: Optional[StrictStr]
    notes: Optional[StrictStr] = ''

    @root_validator
    def validate_hashes_logic(cls, values):
        if (not values.get('commit_hash') and not values.get('distro_hash') and
           not values.get('aggregate_hash')):
            raise InvalidUsage('"Either the aggregate hash or both commit_hash'
                               ' and distro_hash must be provided"',
                               status_code=400)

        if values.get('commit_hash') and not values.get('distro_hash'):
            raise InvalidUsage('If commit_hash is provided, distro_hash '
                               'must be provided too', status_code=400)

        if values.get('distro_hash') and not values.get('commit_hash'):
            raise InvalidUsage('If distro_hash is provided, commit_hash '
                               'must be provided too', status_code=400)

        if ((values.get('aggregate_hash') and values.get('distro_hash')) or
           (values.get('aggregate_hash') and values.get('commit_hash'))):
            raise InvalidUsage('aggregate_hash and commit/distro_hash cannot '
                               'be combined', status_code=400)
        return values
