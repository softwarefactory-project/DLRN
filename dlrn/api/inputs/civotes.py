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
from typing import Optional

from pydantic import BaseModel
from pydantic import NonNegativeInt
from pydantic import root_validator
from pydantic import StrictStr

from dlrn.api.utils import InvalidUsage


class CIVotesInput(BaseModel):
    """Input class that validates request's arguments for civotes get endpoint

    :param int offset: Number of votes to skip (must be positive)
    """
    offset: Optional[NonNegativeInt] = None


class CIVotesDetailInput(BaseModel):
    """Input class that validates request's arguments for civotes_detail

    :param str commit_hash: Commit hash for filtering
    :param str distro_hash: Distro hash for filtering
    :param str component: Component name used for web page template query
    :param str ci_name: CI name used for web page template query
    """
    commit_hash: Optional[StrictStr] = None
    distro_hash: Optional[StrictStr] = None
    component: Optional[StrictStr] = None
    ci_name: Optional[StrictStr] = None

    @root_validator
    def validate_arguments_logic(cls, values):
        if ((not values.get('commit_hash') or not values.get('distro_hash'))
           and not values.get('component') and not values.get("ci_name")):
            raise InvalidUsage("Please specify either commit_hash+distro_hash,"
                               " component or ci_name as parameters.",
                               status_code=400)
        return values


class CIVotesAggDetailInput(BaseModel):
    """Input class that validates request's arguments for civotes_agg_detail

    :param str ref_hash: ref_hash used for web page templating
    :param str ci_name: CI name used for web page templating
    """
    ref_hash: Optional[StrictStr] = None
    ci_name: Optional[StrictStr] = None

    @root_validator
    def validate_arguments_logic(cls, values):
        if not values.get('ref_hash') and not values.get('ci_name'):
            raise InvalidUsage("Please specify either ref_hash or "
                               "ci_name as parameters.", status_code=400)
        return values
