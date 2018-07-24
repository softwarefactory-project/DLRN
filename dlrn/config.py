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
        if cp.has_section('rdoinfo_driver'):
            if cp.has_option('rdoinfo_driver', 'repo'):
                self.rdoinfo_repo = cp.get('rdoinfo_driver', 'repo')

        if cp.has_section('downstream_driver'):
            if cp.has_option('downstream_driver', 'repo'):
                self.rdoinfo_repo = cp.get('downstream_driver', 'repo')
            if cp.has_option('downstream_driver', 'info_files'):
                self.info_files = cp.get('downstream_driver', 'info_files')
            else:
                self.info_files = None
            if cp.has_option('downstream_driver', 'versions_url'):
                self.versions_url = cp.get('downstream_driver',
                                           'versions_url')
            else:
                self.versions_url = None
            if cp.has_option('downstream_driver', 'downstream_distro_branch'):
                self.downstream_distro_branch = cp.get(
                    'downstream_driver', 'downstream_distro_branch')
            else:
                self.downstream_distro_branch = None
            if cp.has_option('downstream_driver', 'downstream_prefix'):
                self.downstream_prefix = cp.get(
                    'downstream_driver', 'downstream_prefix')
            else:
                self.downstream_prefix = None
            if cp.has_option('downstream_driver', 'downstream_prefix_filter'):
                self.downstream_prefix_filter = cp.get(
                    'downstream_driver', 'downstream_prefix_filter')
            else:
                self.downstream_prefix_filter = None

        if cp.has_section('gitrepo_driver'):
            if cp.has_option('gitrepo_driver', 'repo'):
                self.gitrepo_repo = cp.get('gitrepo_driver', 'repo')
            else:
                self.gitrepo_repo = None
            if cp.has_option('gitrepo_driver', 'directory'):
                self.gitrepo_dir = cp.get('gitrepo_driver', 'directory')
            else:
                self.gitrepo_dir = None
            if cp.has_option('gitrepo_driver', 'skip'):
                self.skip_dirs = cp.get('gitrepo_driver', 'skip').split(',')
            else:
                self.skip_dirs = None
            if cp.has_option('gitrepo_driver', 'use_version_from_spec'):
                use_spec = cp.getboolean('gitrepo_driver',
                                         'use_version_from_spec')
                self.use_version_from_spec = use_spec
            else:
                self.use_version_from_spec = False
            if cp.has_option('gitrepo_driver', 'keep_tarball'):
                self.keep_tarball = cp.getboolean('gitrepo_driver',
                                                  'keep_tarball')
            else:
                self.keep_tarball = False
        else:
            self.keep_tarball = False
            self.use_version_from_spec = False
            self.skip_dirs = None
            self.gitrepo_dir = None
            self.gitrepo_repo = None

        if cp.has_section('mockbuild_driver'):
            if cp.has_option('mockbuild_driver', 'install_after_build'):
                self.install_after_build = cp.getboolean(
                    'mockbuild_driver', 'install_after_build')
            else:
                self.install_after_build = True
        else:
            self.install_after_build = True

        # KojiBuildDriver options
        self.koji_krb_principal = None
        self.koji_krb_keytab = None
        self.koji_scratch_build = True
        self.koji_build_target = None
        self.koji_arch = 'x86_64'
        self.koji_exe = 'koji'
        self.fetch_mock_config = False
        self.koji_use_rhpkg = False

        if cp.has_section('kojibuild_driver'):
            if cp.has_option('kojibuild_driver', 'krb_principal'):
                self.koji_krb_principal = cp.get('kojibuild_driver',
                                                 'krb_principal')
                if cp.has_option('kojibuild_driver', 'krb_keytab'):
                    self.koji_krb_keytab = cp.get('kojibuild_driver',
                                                  'krb_keytab')

            if cp.has_option('kojibuild_driver', 'scratch_build'):
                self.koji_scratch_build = cp.getboolean('kojibuild_driver',
                                                        'scratch_build')

            if cp.has_option('kojibuild_driver', 'build_target'):
                self.koji_build_target = cp.get('kojibuild_driver',
                                                'build_target')

            if cp.has_option('kojibuild_driver', 'arch'):
                self.koji_arch = cp.get('kojibuild_driver',
                                        'arch')

            if cp.has_option('kojibuild_driver', 'koji_exe'):
                self.koji_exe = cp.get('kojibuild_driver',
                                       'koji_exe')

            if cp.has_option('kojibuild_driver', 'fetch_mock_config'):
                self.fetch_mock_config = cp.getboolean('kojibuild_driver',
                                                       'fetch_mock_config')

            if cp.has_option('kojibuild_driver', 'use_rhpkg'):
                self.koji_use_rhpkg = cp.getboolean('kojibuild_driver',
                                                    'use_rhpkg')

        if cp.has_section('coprbuild_driver'):
            if cp.has_option('coprbuild_driver', 'coprid'):
                self.coprid = cp.get('coprbuild_driver', 'coprid')
            else:
                self.coprid = None
        else:
            self.coprid = None

        global _config_options
        _config_options = self


def getConfigOptions():
    return _config_options
