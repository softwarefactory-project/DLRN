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
from pydantic import NonNegativeInt
from pydantic import root_validator
from pydantic import StrictStr
from pydantic import validator
from typing import Optional

from dlrn.api.utils import InvalidUsage

MAX_LIMIT = 100


class PromotionsInput(BaseModel):
    """Input class that validates request's arguments for last_tested_repo

    :param str commit_hash(optional) A reference to the commit
    :param str distro_hash(optional): A reference to the distro
    :param str extended_hash(optional): A reference to the extended commit
    :param str aggregate_hash(optional):  A reference to the aggregate hash
    :param str promote_name(optional): Only report promotions for promote_name
    :param int offset(optional): Skip the first X promotions
                                 (only 100 are shown per query)
    :param int limit(optional): Maximum number of entries to return
    :param str component(optional): Only report promotions for this component

    """
    commit_hash: Optional[StrictStr] = None
    distro_hash: Optional[StrictStr] = None
    extended_hash: Optional[StrictStr] = None
    aggregate_hash: Optional[StrictStr] = None
    promote_name: Optional[StrictStr] = None
    offset: Optional[NonNegativeInt] = None
    limit: Optional[NonNegativeInt] = None
    component: Optional[StrictStr] = None

    @validator('limit')
    @classmethod
    def validate_limit(cls, limit):
        # Make sure we do not exceed maximum
        if int(limit) > MAX_LIMIT:
            limit = MAX_LIMIT
        return int(limit)

    @root_validator
    def validate_distro_commit_hash(cls, values):
        if (values.get("distro_hash") and not values.get("commit_hash")) or \
            (not values.get("distro_hash") and values.get("commit_hash")):
            raise InvalidUsage('Both commit_hash and distro_hash must be '
                               'specified if one of them is.',
                               status_code=400)
        return values
