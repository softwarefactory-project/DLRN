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

_config_options = None

# This is how config interface could look - compare with replaced code.
# It might even be moved to individual modules!
# Furthermore, projects.ini can be generated from this.
MODULES_CONFIG = {
    'rdoinfo_driver': {
        'rdoinfo_repo': {'name': 'repo', 'optional': True},
    },
    'downstream_driver': {
        'rdoinfo_repo': {'name': 'repo', 'optional': True},
        'info_files': {},
        'versions_url': {},
        'downstream_distro_branch': {},
        'downstream_prefix': {},
        'downstream_prefix_filter': {},
    },
    'gitrepo_driver': {
        'gitrepo_repo': {'name': 'repo'},
        'gitrepo_dir': {'name': 'directory'},
        'skip_dirs': {'name': 'skip'},
        'use_version_from_spec': {'type': 'boolean'},
        'keep_tarball': {'type': 'boolean'},
    },
    'mockbuild_driver': {
        'install_after_build': {'type': 'boolean', 'default': True},
    },
    'kojibuild_driver': {
        'krb_principal': {},
        'krb_keytab': {},
        'scratch_build': {'type': 'boolean'},
        'build_target': {},
        'koji_arch': {'default': 'x86_64'},
        'koji_exe': {'default': 'koji'},
    },
    'coprbuild_driver': {
        'coprid': {},
    }
}


class ConfigOptions(object):

    def __init__(self, cp):
        # TODO(jruzicka): store this in DEFAULT_CONFIG
        # a la MODULES_CONFIG above
        self.tags = cp.get('DEFAULT', 'tags')
        self.datadir = cp.get('DEFAULT', 'datadir')
        self.gerrit = cp.get('DEFAULT', 'gerrit')
        self.maxretries = cp.getint('DEFAULT', 'maxretries')
        self.baseurl = cp.get('DEFAULT', 'baseurl')
        self.smtpserver = cp.get('DEFAULT', 'smtpserver')
        self.distro = cp.get('DEFAULT', 'distro')
        self.source = cp.get('DEFAULT', 'source')
        self.target = cp.get('DEFAULT', 'target')
        self.reponame = cp.get('DEFAULT', 'reponame')
        self.rsyncdest = cp.get('DEFAULT', 'rsyncdest')
        self.rsyncport = cp.get('DEFAULT', 'rsyncport')
        self.scriptsdir = cp.get('DEFAULT', 'scriptsdir')
        if cp.has_option('DEFAULT', 'configdir'):
            self.configdir = cp.get('DEFAULT', 'configdir')
            if self.configdir == '':
                self.configdir = self.scriptsdir
        else:
            self.configdir = self.scriptsdir
        self.templatedir = cp.get('DEFAULT', 'templatedir')
        self.project_name = cp.get('DEFAULT', 'project_name')
        self.pkginfo_driver = cp.get('DEFAULT', 'pkginfo_driver')
        self.build_driver = cp.get('DEFAULT', 'build_driver')
        self.workers = cp.getint('DEFAULT', 'workers')
        self.gerrit_topic = cp.get('DEFAULT', 'gerrit_topic')
        self.database_connection = cp.get('DEFAULT', 'database_connection')
        self.fallback_to_master = cp.getboolean('DEFAULT',
                                                'fallback_to_master')
        self.release_numbering = cp.get('DEFAULT', 'release_numbering')

        # Handling for optional sections, driver-based
        self.rdoinfo_repo = None
        self.parse_config(MODULES_CONFIG, cp)

        global _config_options
        _config_options = self

    def parse_config(self, config_rules, config_parser):
        for section, rules in config_rules.items():
            if config_parser.has_section(section):
                for option, rule in rules.items():
                    ini_option = rule.get('name', option)
                    if config_parser.has_option(section, ini_option):
                        cp_get_method_name = 'get' + rule.get('type', '')
                        cp_get_method = getattr(config_parser,
                                                cp_get_method_name)
                        val = cp_get_method(section, ini_option)
                        setattr(self, option, val)
                    else:
                        # TODO(jruzicka): assign default depending on
                        # 'default' rule value or 'type' or
                        # leave this unset if 'optional': True
                        raise NotImplemented("TODO")
            else:
                # Section is missing in the config file:
                # TODO(jruzicka): assign defaults the same way as above
                raise NotImplemented("TODO")


def getConfigOptions():
    return _config_options
