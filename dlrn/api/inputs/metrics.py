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
import calendar
import time

from pydantic import BaseModel
from pydantic import StrictStr
from pydantic import validator
from typing import Optional

from dlrn.api.utils import InvalidUsage


class MetricsInput(BaseModel):
    """Input class that validates request's arguments for metrics endpoint

    :param str start_date: Start date for period, in YYYY-mm-dd format (UTC)
    :param str end_date: End date for period, in YYYY-mm-dd format (UTC)
    :param package_name(optional): Return metrics for package_name
    """
    start_date: str
    end_date: str
    package_name: Optional[StrictStr] = None

    @validator('start_date', 'end_date')
    @classmethod
    def validate_datetime(cls, date_value):
        # Convert dates to timestamp
        fmt = '%Y-%m-%d'
        try:
            date_timestamp = int(calendar.timegm(time.strptime(date_value,
                                                               fmt)))
        except ValueError:
            raise InvalidUsage('Invalid date format, it must be YYYY-mm-dd',
                               status_code=400)
        return date_timestamp
