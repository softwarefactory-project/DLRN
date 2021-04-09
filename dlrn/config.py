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
import re

from dlrn.utils import import_class

_config_options = None


def _default_datadir():
    return os.path.realpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "../data"))


def _default_scriptsdir():
    return os.path.realpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "../scripts"))


def _default_templatedir():
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "templates")


DLRN_CORE_CONFIG = {
    'DEFAULT': {
        'tags': {},
        'datadir': {'default': _default_datadir()},
        'gerrit': {},
        'maxretries': {'type': 'int', 'default': 3},
        'baseurl': {},
        'smtpserver': {},
        'distro': {},
        'source': {},
        'target': {},
        'reponame': {},
        'rsyncdest': {'default': ''},
        'rsyncport': {'default': 22},
        'scriptsdir': {'default': _default_scriptsdir()},
        'configdir': {},
        'templatedir': {'default': _default_templatedir()},
        'project_name': {'default': 'RDO'},
        'pkginfo_driver': {'default': 'dlrn.drivers.rdoinfo.RdoInfoDriver'},
        'build_driver': {'default': 'dlrn.drivers.mockdriver.MockBuildDriver'},
        'workers': {'type': 'int', 'default': 1},
        'gerrit_topic': {'default': 'rdo-FTBFS'},
        'database_connection': {'default': 'sqlite:///commits.sqlite'},
        'fallback_to_master': {'type': 'boolean', 'default': True},
        'nonfallback_branches': {'type': 'list',
                                 'default': ['^master$', '^rpm-master$']},
        'release_numbering': {'default': '0.date.hash'},
        'release_minor':     {'default': '0'},
        'custom_preprocess': {'type': 'list'},
        'include_srpm_in_repo': {'type': 'boolean', 'default': True},
        'keep_changelog': {'type': 'boolean', 'default': False},
        'allow_force_rechecks': {'type': 'boolean', 'default': False},
        'use_components': {'type': 'boolean', 'default': False},
        'deps_url': {'default': ''},
    }
}


def setup_logging(debug=False, filename=None):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        filename=filename,
        format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
    # Silence sh module logs
    logging.getLogger("sh.command").setLevel(logging.CRITICAL)


class ConfigOptions(object):

    def __init__(self, cp, overrides=None):
        self.parse_overrides(cp, overrides)
        self.parse_config(DLRN_CORE_CONFIG, cp)
        # dynamic directory defaults
        if not self.configdir:
            self.configdir = self.scriptsdir
        if not self.templatedir:
            self.templatedir = \
                os.path.join(os.path.dirname(os.path.realpath(__file__)),
                             "templates")

        # handling for optional sections, driver-based
        drivers = [
            self.pkginfo_driver,
            self.build_driver,
        ]
        for d in drivers:
            # import driver specific config options
            driver = import_class(d)
            try:
                driver_cfg = driver.DRIVER_CONFIG
            except AttributeError:
                driver_cfg = None
            if driver_cfg:
                self.parse_config(driver_cfg, cp)

        global _config_options
        _config_options = self

    def parse_overrides(self, config_parser, overrides):
        if overrides is None:
            return
        # Now check for any potential overrides
        for rule in overrides:
            rule_match = re.match(r'^(\w+)\.(\w+)=(\w+)$', rule)
            if rule_match is not None:
                section = rule_match.group(1)
                key = rule_match.group(2)
                value = rule_match.group(3)
                if section == 'DEFAULT' or config_parser.has_section(section):
                    if config_parser.has_option(section, key):
                        logging.info("Overriding option %s.%s with value %s" %
                                     (section, key, value))
                        config_parser.set(section, key, value)
                    else:
                        logging.error("Option %s.%s is not present in the"
                                      "configuration file." % (section, key))
                        raise RuntimeError("Unknown config option %s.%s" %
                                           (section, key))

    def parse_config(self, config_rules, config_parser):
        for section, rules in config_rules.items():
            if section == 'DEFAULT' or config_parser.has_section(section):
                for option, rule in rules.items():
                    ini_option = rule.get('name', option)
                    if config_parser.has_option(section, ini_option):
                        _type = rule.get('type', '')
                        if _type == 'list' or _type == 'str':
                            cp_get_method_name = 'get'
                        else:
                            cp_get_method_name = 'get' + _type
                        cp_get_method = getattr(config_parser,
                                                cp_get_method_name)
                        val = cp_get_method(section, ini_option)
                        if _type == 'list':
                            # comma separated list
                            val = val.split(',')
                        setattr(self, option, val)
                    else:
                        self.set_default(option, rule)
            else:
                # section is missing, fill in defaults
                for option, rule in rules.items():
                    self.set_default(option, rule)

    def set_default(self, option, rule):
        if rule.get('ignore_missing'):
            # ignore_missing prevents setting default value
            return
        if 'default' in rule:
            val = rule['default']
        else:
            defaults = {
                'boolean': False,
                'int': 0,
                'str': '',
                'list': [],
            }
            val = None
            _type = rule.get('type')
            if _type and _type in defaults:
                val = defaults[_type]
        setattr(self, option, val)


def getConfigOptions():
    return _config_options
