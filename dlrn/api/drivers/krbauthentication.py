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
from functools import wraps

import logging
import os
import time

from flask import request
from flask_httpauth import HTTPAuth
try:
    import gssapi
except ModuleNotFoundError:
    gssapi = None
try:
    from ipalib import api
    from ipalib.errors import ACIError
    from ipalib.errors import CCacheError
    from ipalib.errors import KerberosError
    from ipalib.errors import NetworkError
except ModuleNotFoundError:
    api = None
import sh
from sh import ErrorReturnCode
from werkzeug.datastructures import Authorization

from dlrn.api import app

log_auth = logging.getLogger("logger_auth")
log_api = logging.getLogger("logger_dlrn")

IPALIB_CONTEXT = 'dlrn-api'
MAX_RETRY = app.config['CONN_MAX_RETRY']


def retry_on_error(custom_error=None, action_msg="", success_msg=""):
    def _retry_on_error(f):
        @wraps(f)
        def retry_on_error_manager(self):
            success = False
            retry_index = 0
            while not success and retry_index < MAX_RETRY:
                log_api.info("[%s], %s", retry_index, action_msg)
                try:
                    success = f(self)
                except custom_error as e:
                    log_api.exception("Exception occurred %s" % e)
                    retry_index += 1
                    time.sleep(2)
                except Exception as e:
                    log_api.exception(e)
                    raise

            if retry_index == MAX_RETRY:
                log_api.error("Maximum retries executed")
            if not success:
                raise Exception("Failed to complete operation")

            log_api.info(success_msg)
            return success

        return retry_on_error_manager
    return _retry_on_error


class IPAAuthorization:
    # Optional module installed by Kerberos extras_require
    api = api

    def __init__(self):
        log_api.debug("Starting IPAAuthorization")
        self._username = None
        if self.api is None:
            raise ModuleNotFoundError("Kerberos auth not enabled due"
                                      " to missing ipalib dependency")
        log_api.debug("IPAAuthorization started")

    def set_username(self, username):
        self._username = username

    def get_username(self):
        return self._username

    def disconnect_from_ipa(self):
        try:
            self.api.Backend.rpcclient.disconnect()
            log_api.debug("Disconnected from IPA server")
        except Exception as e:
            log_api.error("Error while disconnecting from IPA: %s" % e)

    @retry_on_error(custom_error=KerberosError,
                    action_msg="Connecting to IPA for authorization...",
                    success_msg="Connected succesfully to IPA server")
    def connect_to_ipa_server(self):
        if "context" not in self.api.env or \
           self.api.env.context != IPALIB_CONTEXT:
            self.api.bootstrap(context=IPALIB_CONTEXT)
            self.api.finalize()
        if not api.Backend.rpcclient.isconnected():
            self.api.Backend.rpcclient.connect()
        return True

    @retry_on_error(custom_error=ErrorReturnCode,
                    action_msg="Retrieving valid kerberos token...",
                    success_msg="Valid kerberos token retrieved")
    def retrieve_kerb_ticket(self):
        keytab_path = app.config['KEYTAB_PATH']
        keytab_princ = app.config['KEYTAB_PRINC']
        try:
            kinit = sh.kinit.bake()
            kinit('-kt', keytab_path, keytab_princ)
            return True
        except ErrorReturnCode:
            raise

    @retry_on_error(custom_error=(gssapi.raw.misc.GSSError, CCacheError,
                                  ACIError, KerberosError,
                                  NetworkError),
                    action_msg="Returning user roles...",
                    success_msg="Roles returned successfully")
    def execute_user_show(self):
        result = self.api.Command.user_show(self.get_username())
        return result['result']['memberof_group']

    def return_user_roles(self):
        try:
            self.retrieve_kerb_ticket()
            self.connect_to_ipa_server()
            roles = self.execute_user_show()
            self.disconnect_from_ipa()
        except Exception:
            raise
        return roles


class KrbAuthentication(HTTPAuth):
    # Optional module installed by Kerberos extras_require
    gssapi = gssapi

    def __init__(self, scheme='Negotiate', realm=None, header=None):
        super(KrbAuthentication, self).__init__(scheme=scheme, realm=realm,
                                                header=header)
        log_api.debug("Starting KrbAuthentication")
        self.verify_token_callback = self.verify_user
        self.get_user_roles_callback = self.get_user_roles
        # HTTP keytab for decrypting the token.
        os.environ["KRB5_KTNAME"] = "FILE:" + app.config['HTTP_KEYTAB_PATH']
        log_api.debug("KrbAuthentication started")

    def _start_authorization(self):
        try:
            self.ipa = IPAAuthorization()
        except ModuleNotFoundError:
            raise

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
            self._start_authorization()
        except ModuleNotFoundError as e:
            log_api.exception(e)
            raise
        self.ipa.set_username(username)
        try:
            groups = self.ipa.return_user_roles()
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
