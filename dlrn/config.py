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
        'rsyncdest': {},
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
        'release_numbering': {'default': '0.date.hash'},
    }
}

MODULES_CONFIG = {
    'rdoinfo_driver': {
        'rdoinfo_repo': {'name': 'repo', 'ignore_missing': True},
    },
    'downstream_driver': {
        'rdoinfo_repo': {'name': 'repo', 'ignore_missing': True},
        'info_files': {},
        'versions_url': {},
        'downstream_distro_branch': {},
        'downstream_prefix': {},
        'downstream_prefix_filter': {},
    },
    'gitrepo_driver': {
        'gitrepo_repo': {'name': 'repo'},
        'gitrepo_dir': {'name': 'directory'},
        'skip_dirs': {'name': 'skip', 'type': 'list'},
        'use_version_from_spec': {'type': 'boolean'},
        'keep_tarball': {'type': 'boolean'},
    },
    'mockbuild_driver': {
        'install_after_build': {'type': 'boolean', 'default': True},
    },
    'kojibuild_driver': {
        'koji_krb_principal': {'name': 'krb_principal'},
        'koji_krb_keytab': {'name': 'krb_keytab'},
        'koji_scratch_build': {'name': 'scratch_build', 'type': 'boolean',
                               'default': True},
        'koji_build_target': {'name': 'build_target'},
        'koji_arch': {'name': 'arch', 'default': 'x86_64'},
        'koji_exe': {'default': 'koji'},
        'fetch_mock_config': {'type': 'boolean'}
    },
    'coprbuild_driver': {
        'coprid': {},
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
                             "templates"),

        # handling for optional sections, driver-based
        self.rdoinfo_repo = None
        self.parse_config(MODULES_CONFIG, cp)

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
            val = None
            _type = rule.get('type')
            if _type:
                if _type == 'boolean':
                    val = False
                elif _type == 'int':
                    val = 0
                elif _type == 'str':
                    val = ''
                elif _type == 'list':
                    val = []
        setattr(self, option, val)


def getConfigOptions():
    return _config_options
