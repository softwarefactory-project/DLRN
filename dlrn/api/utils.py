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

auth = HTTPBasicAuth()


@auth.verify_password
def verify_pw(username, password):
    log = logging.getLogger("logger_auth")
    session = getSession(app.config['DB_PATH'])
    user = session.query(User).filter(User.username == username).first()
    if user is not None:
        if passlib.hash.sha512_crypt.verify(password, user.password):
            log.info('"User": %s, "event": login, "success": true, '
                     '"path": %s, "method": %s', username, request.path,
                     request.method)
            return True
    log.info('"User": %s, "event": login, "success": false, "path": %s, '
             '"method": %s', username, request.path, request.method)
    return False


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


class RepoDetail(object):
    def __init__(self):
        self.commit_hash = None
        self.distro_hash = None
        self.distro_hash_short = None
        self.success = 0
        self.failure = 0
        self.timestamp = 0
        self.component = None


class AggDetail(object):
    def __init__(self):
        self.ref_hash = None
        self.success = 0
        self.failure = 0
        self.timestamp = 0
