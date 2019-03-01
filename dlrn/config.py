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

from dlrn.utils import import_class

_config_options = None

DLRN_CORE_CONFIG = {
    'DEFAULT': {
        'tags': {},
        'datadir': {},
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
        'scriptsdir': {},
        'configdir': {},
        'templatedir': {},
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
        'custom_preprocess': {'type': 'list'},
        'include_srpm_in_repo': {'type': 'boolean', 'default': True},
    }
}


class ConfigOptions(object):

    def __init__(self, cp):
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
