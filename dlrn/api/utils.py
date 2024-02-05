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


class ConfigurationValidator(object):
    def __init__(self, config):
        self.configuration_errors = {}
        self.config = config
        self.validate_config()

    def is_valid(self):
        """Check if the configuration is valid

        It is done by checking if there are any sections with errors.

        :returns: bool: Returns true if no error found, false otherwise.
        """
        has_errors = False
        for section in self.configuration_errors:
            has_errors = has_errors | bool(self.configuration_errors[section])
        return not has_errors

    def __repr__(self):
        """Prepare the object to represent the status of the validation

        The output is a list of errors for each validated section in the
        following format:

        ERROR: Found the following errors:
            Section: Section_A
                Section_A.error1
                Section_A.error2
                Section_A.error3
            Section: Section_B
                Section_B.error1
        or if not error found:
            No errors were found during the API config validation.

        :returns: The validation output information
        """
        output = ""
        for section in self.configuration_errors:
            if bool(self.configuration_errors[section]):
                output = output + f"\t Section: {section}\n"
                for error in self.configuration_errors[section]:
                    output = output + f"\t\t{error}\n"
        if output:
            return "Found the following errors:\n" + output
        else:
            return "No errors were found during the API config validation."

    def validate_config(self):
        """Start the validation of the configuration of the drivers.

        """
        self.validate_api_drivers()

    def validate_api_roles(self, required_authorization=False):
        """Validates role configuration when authorization is required.

        Sets the found error in self.configuration_errors under the section
        API_ROLES_ERROR.

        Authorization is required when using KrbAuthentication. Valid
        cases are:
        - API_READ_WRITE_ROLES and API_READ_ONLY_ROLES
        - ALLOWED_GROUPS (deprecated)

        :param bool required_authorization: True if authorization is
        required based on selected authentication driver, otherwise False
        """
        error_section = 'API_ROLES_ERROR'
        self.configuration_errors[error_section] = []
        has_read_roles_key = 'API_READ_ONLY_ROLES' in self.config.keys()
        has_write_roles_key = 'API_READ_WRITE_ROLES' in self.config.keys()
        has_allowed_group_roles_key = 'ALLOWED_GROUP' in self.config.keys()
        if (not has_read_roles_key and has_write_roles_key) or \
            (has_read_roles_key and not has_write_roles_key):
            error_message = "Declare both or none from API_READ_WRITE_ROLES " \
                "and API_READ_ONLY_ROLES."
            self.configuration_errors[error_section].append(error_message)
        elif required_authorization and not has_read_roles_key and \
            not has_write_roles_key and not has_allowed_group_roles_key:
            error_message = "The KrbAuthentication driver requires setting" \
                " either ALLOWED_GROUP or both API_READ_WRITE_ROLES and " \
                "API_READ_ONLY_ROLES."
            self.configuration_errors[error_section].append(error_message)

    def validate_api_drivers(self):
        """Validates the driver configuration based on the driver selected.

        """
        if 'AUTHENTICATION_DRIVERS' not in self.config.keys() or \
            'DBAuthentication' in self.config['AUTHENTICATION_DRIVERS']:
            self.validate_dbauthentication_driver()
        if 'AUTHENTICATION_DRIVERS' in self.config.keys() and \
            'KrbAuthentication' in self.config['AUTHENTICATION_DRIVERS']:
            self.validate_KrbAuthentication_driver()

    def validate_dbauthentication_driver(self):
        """Validates the configuration of the DBAuthentication driver.

        Sets the found error in self.configuration_errors under the section
        DBAUTH_DRIVER_ERROR.

        It also starts with the validation of the roles configuration.
        """
        error_section = 'DBAUTH_DRIVER_ERROR'
        self.configuration_errors[error_section] = []
        if 'DB_PATH' not in self.config.keys():
            error_message = "No DB_PATH in the app configuration."
            self.configuration_errors[error_section].append(error_message)
        self.validate_api_roles(required_authorization=False)

    def validate_KrbAuthentication_driver(self):
        """Validates the configuration of the KrbAuthentication driver.

        Sets the found error in self.configuration_errors under the section
        KRBAUTH_DRIVER_ERROR.

        It also starts with the validation of the roles configuration.
        """
        error_section = 'KRBAUTH_DRIVER_ERROR'
        self.configuration_errors[error_section] = []
        if 'HTTP_KEYTAB_PATH' not in self.config.keys():
            error_message = "No HTTP_KEYTAB_PATH in the app configuration."
            self.configuration_errors[error_section].append(error_message)
        if 'KEYTAB_PATH' not in self.config.keys():
            error_message = "No KEYTAB_PATH in the app configuration."
            self.configuration_errors[error_section].append(error_message)
        if 'KEYTAB_PRINC' not in self.config.keys():
            error_message = "No KEYTAB_PRINC in the app configuration."
            self.configuration_errors[error_section].append(error_message)
        if 'CONN_MAX_RETRY' not in self.config.keys() or \
           self.config["CONN_MAX_RETRY"] < 1:
            # TODO(evallesp): Adds warning log about the final value
            self.config["CONN_MAX_RETRY"] = 5
        if 'IPA_CACHE_TIMEOUT' not in self.config.keys() or \
           self.config["IPA_CACHE_TIMEOUT"] < 1 or \
           self.config["IPA_CACHE_TIMEOUT"] > 86400:
            # TODO(evallesp): Adds warning log about the final value
            self.config["IPA_CACHE_TIMEOUT"] = 8 * 3600
        self.validate_api_roles(required_authorization=True)
