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
import logging
import logging.config as logging_config
import os

from flask import Flask

from dlrn.api.api_logging import setup_dict_config
from dlrn.api.utils import ConfigurationValidator

app = Flask(__name__)
app.config.from_object('dlrn.api.config')
try:
    app.config.from_pyfile(os.environ['CONFIG_FILE'], silent=True)
except KeyError:
    pass


def setup_api_logging(config):
    log_dictConfig = setup_dict_config(app.config)
    logging_config.dictConfig(log_dictConfig)


setup_api_logging(app.config)
log_api = logging.getLogger("logger_dlrn")
configuration_validation = ConfigurationValidator(app.config)
if configuration_validation.is_valid():
    log_api.debug(configuration_validation)
    # TODO(evallesp): Change how we initialize the API to move
    # imports to the top. If the config is valid, then we start
    # the whole API
    from dlrn.api import dlrn_api  # noqa
    from dlrn.api import graphql  # noqa
    from dlrn.api import prom_metrics  # noqa
else:
    log_api.error(configuration_validation)
    raise Exception
