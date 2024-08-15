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
from pydantic import StrictStr
from typing import Optional


class AggStatusInput(BaseModel):
    """Input class that validates request's arguments for agg_status endpoint

    :param str aggregate_hash: A reference to the aggregate hash
    :param bool success(optional): Only report successful/unsuccessful votes
    """
    aggregate_hash: StrictStr
    success: Optional[bool]
