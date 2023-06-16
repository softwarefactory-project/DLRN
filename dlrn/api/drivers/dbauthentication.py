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

from flask import request
from flask_httpauth import HTTPBasicAuth
import passlib.hash

from dlrn.api import app
from dlrn.db import getSession
from dlrn.db import User


log_auth = logging.getLogger("logger_auth")
log_api = logging.getLogger("logger_dlrn")


class DBAuthentication(HTTPBasicAuth):
    def __init__(self, scheme='Basic', realm=None, header=None):
        super(HTTPBasicAuth, self).__init__(scheme=scheme, realm=realm,
                                            header=header)
        self.verbose_build = False
        self.verify_password_callback = self.verify_pw

    def verify_pw(self, username, password):
        allowed = False
        session = None
        if 'DB_PATH' not in app.config.keys():
            log_api.error("No DB_PATH in the app configuration.")
        else:
            session = getSession(app.config['DB_PATH'])
        if not username or not password:
            log_api.error("No user or password in the request headers.")
        elif session is not None:
            user = session.query(User).filter(User.username == username) \
                                      .first()
            if user is not None:
                if passlib.hash.sha512_crypt.verify(password, user.password):
                    log_auth.info('"User": %s, "event": login, "success": '
                                  'true, "path": %s, "method": %s', username,
                                  request.path, request.method)
                    allowed = True
                else:
                    log_auth.info('"User": %s, "event": login, "success": '
                                  'false, "path": %s, "method": %s', username,
                                  request.path, request.method)
        return allowed
