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
import os

from flask import has_request_context
from flask import request

# 1024 * 1024 * 15
HANDLER_MAX_BYTES = 15728640


def get_config(config, var_name):
    return config.get(var_name, os.environ.get(var_name, False))


def create_rotating_file_handler_dict(name, log_path):
    handler_dict = dict()
    result = dict()
    handler_dict["class"] = 'logging.handlers.RotatingFileHandler'
    handler_dict["filename"] = log_path
    handler_dict["backupCount"] = 3
    handler_dict["maxBytes"] = HANDLER_MAX_BYTES
    handler_dict["formatter"] = 'default'
    result[name] = handler_dict
    return result


def create_logger_dict(name, handler_name, log_level):
    logger_dict = dict()
    result = dict()
    logger_dict["level"] = log_level
    logger_dict["handlers"] = [handler_name]
    logger_dict["propagate"] = False
    result[name] = logger_dict
    return result


def setup_dict_config(config):
    api_log_config = {
        'version': 1,
        'formatters': {
            'default': {
                '()': FlaskRequestFormatter,
                'format': '"timestamp": %(asctime)s "src": %(remote_addr)s'
                          ' %(levelname)s: %(message)s',
            },
        },
        'handlers': {
        },
        'loggers': {
            'root': {
                'level': 'INFO',
            },
        }
    }

    dlrn_debug = "DEBUG" if get_config(config, "DLRN_DEBUG") \
        else "INFO"
    dlrn_log_file = get_config(config, "DLRN_LOG_FILE")
    api_auth_debug = "DEBUG" if get_config(config, "API_AUTH_DEBUG") \
        else "INFO"
    api_auth_log_file = get_config(config, "API_AUTH_LOG_FILE")
    api_auth_handler_name = "file_auth"
    api_auth_logger_name = "logger_auth"
    api_dlrn_handler_name = "file_dlrn"
    api_dlrn_logger_name = "logger_dlrn"

    if dlrn_log_file:
        file_dlrn_handler = create_rotating_file_handler_dict(
            api_dlrn_handler_name, dlrn_log_file)
        dlrn_logger = create_logger_dict(
            api_dlrn_logger_name, api_dlrn_handler_name, dlrn_debug)
        api_log_config['handlers'].update(file_dlrn_handler)
        api_log_config['loggers'].update(dlrn_logger)
    else:
        api_log_config["loggers"]["root"]["level"] = dlrn_debug

    if api_auth_log_file:
        file_auth_handler = create_rotating_file_handler_dict(
            api_auth_handler_name, api_auth_log_file)
        auth_logger = create_logger_dict(
            api_auth_logger_name, api_auth_handler_name, api_auth_debug)
        api_log_config['handlers'].update(file_auth_handler)
        api_log_config['loggers'].update(auth_logger)

    return api_log_config


# FlaskRequestFormatter took from flask-container-scaffold project.
# Not python 2 compatible.
# https://github.com/release-depot/flask-container-scaffold \
# /blob/main/src/flask_container_scaffold/logging.py
class FlaskRequestFormatter(logging.Formatter):
    """A Formatter logging class to add IP information to the log records.

    Usage example::
      from flask_container_scaffold.logging import FlaskRequestFormatter
      dictConfig({
          'version': 1,
          'formatters': {
              'default': {
                  '()': FlaskRequestFormatter,
                  'format': '[%(asctime)s] %(remote_addr)s %(levelname)s:
                  %(message)s',
              },
          },
          ...
      })
    """

    def get_ip_from_forwarded(self, field):
        # RFC 7239 defines the following format for the Forwarded field:
        # for=12.34.56.78;host=example.com;proto=https, for=23.45.67.89
        # In testing, the first IP has consistently been the real user IP.
        forwarded = field.split(",")[0]
        for value in forwarded.split(";"):
            if value.startswith("for="):
                return value.split("=")[1]
        else:
            return None

    def format(self, record):
        if has_request_context():
            # HTTP_FORWARDED seems to be the most reliable way to get the
            # user real IP.
            forwarded = request.environ.get('HTTP_FORWARDED')
            if forwarded:
                ip = self.get_ip_from_forwarded(forwarded)
                record.remote_addr = ip or request.remote_addr
            else:
                record.remote_addr = request.remote_addr
        else:
            record.remote_addr = "-"

        return super().format(record)
