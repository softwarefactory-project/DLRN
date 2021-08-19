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

import os

from flask import Flask

app = Flask(__name__)
app.config.from_object('dlrn.api.config')
try:
    app.config.from_pyfile(os.environ['CONFIG_FILE'], silent=True)
except KeyError:
    pass

from dlrn.api import dlrn_api  # noqa
from dlrn.api import graphql # noqa
from dlrn.api import prom_metrics # noqa
from dlrn.config import setup_logging  # noqa


setup_logging(os.environ.get("DLRN_DEBUG"), os.environ.get("DLRN_LOG_FILE"))
