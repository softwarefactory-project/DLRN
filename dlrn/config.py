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


class ConfigOptions(object):

    def __init__(self, cp):
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

        # This is how config interface could look - compare with replaced code.
        # It might even be moved to individual modules!
        # Furthermore, projects.ini can be generated from this.

        RDOINFO_DRIVER_CONFIG = {
            'rdoinfo_driver': {
                'rdoinfo_repo': Opt(name='repo', missing='ignore'),
            }
        }
        DOWNSTREAM_DRIVER_CONFIG = {
            'downstream_driver': {
                'rdoinfo_repo': Opt(name='repo', missing='ignore'),
                'info_files': Opt(),
                'versions_url': Opt(),
                'downstream_distro_branch': Opt(),
                'downstream_prefix': Opt(),
                'downstream_prefix_filter': Opt(),
            }
        }
        GITREPO_DRIVER_CONFIG = {
            'gitrepo_driver': {
                'gitrepo_repo': Opt(name='repo'),
                'gitrepo_dir': Opt(name='directory'),
                'skip_dirs': Opt(name='skip'),
                'use_version_from_spec': Opt(type='boolean'),
                'keep_tarball': Opt(type='boolean'),
            }
        }
        MOCKBUILD_DRIVER_CONFIG = {
            'mockbuild_driver': {
                'install_after_build': Opt(type='boolean', default=True),
            }
        }
        KOJIBUILD_DRIVER_CONFIG = {
            'kojibuild_driver': {
                'krb_principal': Opt(),
                'krb_keytab': Opt(),
                'scratch_build': Opt(type='boolean'),
                'build_target': Opt(),
                'koji_arch': Opt(default='x86_64'),
                'koji_exe': Opt(default='koji'),
            }
        }
        COPRBUILD_DRIVER_CONFIG = {
            'mockbuild_driver': {
                'coprid': Opt(),
            }
        }
        # TODO(jruzicka): self.parse_config(RDOINFO_DRIVER_CONFIG) etc.

        global _config_options
        _config_options = self


def getConfigOptions():
    return _config_options
