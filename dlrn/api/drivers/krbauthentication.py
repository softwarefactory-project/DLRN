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
import base64
import logging
import os

from flask import request
from flask_httpauth import HTTPAuth
try:
    import gssapi
except ModuleNotFoundError:
    gssapi = None
try:
    from ipalib import api
    from ipalib.errors import PublicError
except ModuleNotFoundError:
    api = None
import sh
from werkzeug.datastructures import Authorization

from dlrn.api import app
from dlrn.api.utils import ConfigError

log_auth = logging.getLogger("logger_auth")
log_api = logging.getLogger("logger_dlrn")

IPALIB_CONTEXT = 'dlrn-api'
MAX_KINIT_RETRY = 3


class IPAAuthorization:
    # Optional module installed by Kerberos extras_require
    api = api

    def __init__(self):
        if self.api is None:
            raise ModuleNotFoundError("Kerberos auth not enabled due"
                                      " to missing ipalib dependency")
        kinit_success = False
        retry_index = 0
        while not kinit_success and retry_index < MAX_KINIT_RETRY:
            log_api.info("[%s], Retrieving valid kerberos token..." %
                         retry_index)
            try:
                kinit_success = self.retrieve_kerb_ticket()
            except ConfigError as e:
                log_api.exception(e)
                raise ConfigError
            except Exception as e:
                log_api.exception("Exception occurred while retrieving"
                                  " a valid kerberos token: %s" % e)
                retry_index += 1

        if retry_index == MAX_KINIT_RETRY:
            log_api.exception("Maximum retries for retrieving valid"
                              " kerberos token executed")
        if not kinit_success:
            raise Exception

        log_api.info("Valid kerberos token retrieved")

        try:
            # Avoid to initialize twice.
            if "context" not in self.api.env or \
               self.api.env.context != IPALIB_CONTEXT:
                self.api.bootstrap(context=IPALIB_CONTEXT)
                self.api.finalize()
            if not api.Backend.rpcclient.isconnected():
                self.api.Backend.rpcclient.connect()
        except Exception as e:
            log_api.exception("Exception occurred while Initializing"
                              " connection to IPA: %s" % e)
            raise

    def disconnect_from_ipa(self):
        try:
            self.api.Backend.rpcclient.disconnect()
        except Exception as e:
            log_api.exception("Error while disconnecting from IPA: %s" % e)

    def return_user_roles(self, username):
        try:
            result = self.api.Command.user_show(username)
            return result['result']['memberof_group']
        except PublicError as e:
            raise PublicError(e)

    def retrieve_kerb_ticket(self):
        if 'KEYTAB_PATH' not in app.config.keys():
            raise ConfigError("No keytab_path in the app configuration")
        if 'KEYTAB_PRINC' not in app.config.keys():
            raise ConfigError("No keytab_princ in the app configuration")
        keytab_path = app.config['KEYTAB_PATH']
        keytab_princ = app.config['KEYTAB_PRINC']
        try:
            kinit = sh.kinit.bake()
            kinit('-kt', keytab_path, keytab_princ)
            return True
        except Exception as e:
            raise (Exception("Exception while retrieving valid "
                             "kerberos ticket: %s" % e))


class KrbAuthentication(HTTPAuth):
    # Optional module installed by Kerberos extras_require
    gssapi = gssapi

    def __init__(self, scheme='Negotiate', realm=None, header=None):
        super(KrbAuthentication, self).__init__(scheme=scheme, realm=realm,
                                                header=header)
        self.verify_token_callback = self.verify_user
        self.get_user_roles_callback = self.get_user_roles
        if 'HTTP_KEYTAB_PATH' not in app.config.keys():
            raise ConfigError("No http_keytab_path in the app configuration")
        # HTTP keytab for decrypting the token.
        os.environ["KRB5_KTNAME"] = "FILE:" + app.config['HTTP_KEYTAB_PATH']

    def get_user(self, token):
        if self.gssapi is None:
            raise ModuleNotFoundError("Kerberos auth not enabled due to "
                                      "missing gssapi dependency")
        sc = self.gssapi.SecurityContext(usage="accept")
        token = token if token != "" else None

        try:
            while not sc.complete:
                output_token = sc.step(token)
                if not output_token:
                    break
        except gssapi.raw.exceptions.InvalidTokenError:
            log_api.error('Invalid token while accessing "path": %s, '
                          '"method": %s', request.path, request.method)
            return None
        if not sc.complete:
            user = None
        else:
            user = str(sc.initiator_name).split("@")[0]
        return user

    def get_user_roles(self, username):
        try:
            ipa = IPAAuthorization()
            groups = ipa.return_user_roles(username)
        except Exception as e:
            log_api.error("Error while retrieving user's roles: %s" % e)
            raise
        return groups

    def verify_user(self, token):
        username = None
        if token:
            try:
                username = self.get_user(base64.b64decode(token))
            except ModuleNotFoundError as e:
                log_api.exception(e)
                raise
            except Exception:
                pass
        return username

    def authorize(self, role, user, auth):
        success = super().authorize(role, user, auth)
        if success:
            log_auth.info('"User": %s, "event": login, "success": '
                          'true, "path": %s, "method": %s', user,
                          request.path, request.method)
        else:
            log_auth.info('"User": %s, "event": login, "success": '
                          'false, "path": %s, "method": %s',
                          user, request.path, request.method)
        return success

    def authenticate(self, auth, password):
        # This overrides authenticate from flask_httpauth method.
        # Taken from HTTPTokenAuth as It wasn't syncing the token properly.
        token = ""
        if not auth:
            log_api.error("Error in the request. No token in the header.")
            return False
        if "token" in auth:
            token = auth['token']
        if self.verify_token_callback:
            return self.ensure_sync(self.verify_token_callback)(token)

    def get_auth(self):
        # Parent method doesn't parse the Kerberos token properly.
        # Adding the token to the dict key 'parameters' instead of 'token'
        auth = None
        if 'Authorization' in request.headers:
            try:
                # Expected to receive "Negotiate: Token" inside authorization.
                auth_type, token = request.headers['Authorization'].split(
                    None, 1)
                auth = Authorization(auth_type, {'token': token})
            except (ValueError, KeyError) as e:
                log_api.error("Error in Authorization header: %s", e)
        return auth
