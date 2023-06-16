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

from flask_httpauth import MultiAuth
import stevedore

from dlrn.utils import import_class


DEFAULT_DRIVER = "dlrn.api.drivers.dbauthentication.DBAuthentication"
NAMESPACE = 'dlrn.api.drivers'
logger = logging.getLogger("logger_dlrn")


class Auth:

    def __init__(self, config):
        self.auth_multi = None
        self._setup_api_auth(config)

    def _get_default_driver(self):
        return DEFAULT_DRIVER

    def _setup_api_auth(self, config):
        auth_drivers = []
        if 'AUTHENTICATION_DRIVERS' not in config.keys():
            config['AUTHENTICATION_DRIVERS'] = []

        self._ext_mgr = stevedore.ExtensionManager(
            NAMESPACE,
            invoke_on_load=True)

        for driver_name in config['AUTHENTICATION_DRIVERS']:
            try:
                auth_drivers.append(self._ext_mgr[driver_name].obj)
                logger.info("Added auth driver: %s", driver_name)
            except KeyError as faulty_driver:
                logger.error("Driver not found: %s", faulty_driver)
        if len(auth_drivers) == 0:
            try:
                default_driver = self._get_default_driver()
                logger.info("Trying to load default auth driver: %s",
                            default_driver)
                auth_drivers.append(import_class(default_driver)())
                logger.info("Default auth driver loaded.")
            except (ModuleNotFoundError, ImportError):
                logger.error("Error, driver not found. No auth driver loaded")
                exit(1)
        self.auth_multi = MultiAuth(*auth_drivers)
