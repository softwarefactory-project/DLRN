# -*- coding: utf-8 -*-

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

import mock
import os
import sh
import shutil
import stat
import tempfile

from dlrn.config import ConfigOptions
from dlrn import db
from dlrn.drivers.kojidriver import KojiBuildDriver
from dlrn.tests import base
from six.moves import configparser
from time import localtime
from time import strftime


def _mocked_listdir(directory):
    return ['python-pysaml2-3.0-1a.el7.centos.src.rpm']


def _mocked_time():
    return float(1533293385.545039)


def _mocked_call(*args, **kwargs):
    if args[0] == '--pretty=format:%H %ct':
        # Returned when called git log
        return '1 2'
    return True


def _mocked_call_and_timeout(*args, **kwargs):
    if args[0] == '--pretty=format:%H %ct':
        # Returned when called git log
        return '1 2'
    if args[0] == 'build':
        # Returned when called rhpkg build
        raise sh.TimeoutException("Timeout", "")
    return True


def _mocked_list_tasks(*args, **kwargs):
    return ["45133830 20   osp-build-staging    OPEN     noarch\
                build (rhos-17.0-rhel-9-trunk-candidate, \
                python-pysaml2-3.0-1a.el7.centos.src.rpm)"]


@mock.patch('sh.restorecon', create=True)
@mock.patch('sh.env', create=True)
@mock.patch('os.listdir', side_effect=_mocked_listdir)
class TestDriverKoji(base.TestCase):
    def setUp(self):
        super(TestDriverKoji, self).setUp()
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set("DEFAULT", "build_driver",
                   "dlrn.drivers.kojidriver.KojiBuildDriver")
        self.config = ConfigOptions(config)
        self.config.koji_krb_principal = 'test@example.com'
        self.config.koji_krb_keytab = '/home/test/test.keytab'
        self.config.koji_scratch_build = True
        self.config.koji_build_target = 'build-target'
        self.temp_dir = tempfile.mkdtemp()
        self.config.datadir = self.temp_dir
        # Create fake build log
        with open("%s/kojibuild.log" % self.temp_dir, 'a') as fp:
            fp.write("Created task: 1234")
        # In the rhpkg case, we need to create a full dir structure
        self.rhpkg_extra_dir = "%s/repos/12/34/1234567890abcdef_1_12345678"\
                               % self.temp_dir
        os.makedirs(self.rhpkg_extra_dir)
        with open("%s/rhpkgbuild.log"
                  % self.rhpkg_extra_dir, 'a') as fp:
            fp.write("Created task: 5678")
        # Another full-dir structure for the long extended hash test
        self.rhpkg_extra_dir_2 = (
            "%s/repos/12/34/1234567890abcdef_1_12345678_abcdefgh" %
            self.temp_dir)
        os.makedirs(self.rhpkg_extra_dir_2)
        with open("%s/rhpkgbuild.log"
                  % self.rhpkg_extra_dir_2, 'a') as fp:
            fp.write("Created task: 5678")
        # Another full-dir structure for the long extended hash test
        # with downstream driver
        self.rhpkg_extra_dir_3 = (
            "%s/repos/12/34/1234567890abcdef_fedcba09_1_1" %
            self.temp_dir)
        os.makedirs(self.rhpkg_extra_dir_3)
        with open("%s/rhpkgbuild.log"
                  % self.rhpkg_extra_dir_3, 'a') as fp:
            fp.write("Created task: 5678")
        # Create a fake rhpkg binary
        with open("%s/rhpkg" % self.temp_dir, 'a') as fp:
            fp.write("true")
        os.chmod("%s/rhpkg" % self.temp_dir,
                 stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
        os.environ['PATH'] = self.temp_dir + ':' + os.environ['PATH']

    def tearDown(self):
        super(TestDriverKoji, self).tearDown()
        shutil.rmtree(self.temp_dir)

    def test_build_package(self, ld_mock, env_mock, rc_mock):
        driver = KojiBuildDriver(cfg_options=self.config)
        driver.build_package(output_directory=self.temp_dir)

        expected = [mock.call(['koji',
                               '--principal', self.config.koji_krb_principal,
                               '--keytab', self.config.koji_krb_keytab,
                               'build', '--wait',
                               self.config.koji_build_target,
                               '%s/python-pysaml2-3.0-1a.el7.centos.src.rpm' %
                               self.temp_dir],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              scratch=True,
                              _cwd=self.temp_dir,
                              _env=mock.ANY),
                    mock.call(['koji', 'download-task', '--logs', '1234'],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              _cwd=self.temp_dir,
                              _env=mock.ANY)]
        # 1- koji build (handled by env_mock)
        # 2- koji download (handled by env_mock)
        # 3- restorecon (handled by rc_mock)
        self.assertEqual(env_mock.call_count, 2)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(env_mock.call_args_list, expected)

    def test_build_package_no_scratch(self, ld_mock, env_mock, rc_mock):
        self.config.koji_scratch_build = False
        driver = KojiBuildDriver(cfg_options=self.config)
        driver.build_package(output_directory=self.temp_dir)

        expected = [mock.call(['koji',
                               '--principal', self.config.koji_krb_principal,
                               '--keytab', self.config.koji_krb_keytab,
                               'build', '--wait',
                               self.config.koji_build_target,
                               '%s/python-pysaml2-3.0-1a.el7.centos.src.rpm' %
                               self.temp_dir],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              scratch=False,
                              _cwd=self.temp_dir,
                              _env=mock.ANY),
                    mock.call(['koji', 'download-task', '--logs', '1234'],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              _cwd=self.temp_dir,
                              _env=mock.ANY)]
        # 1- koji build (handled by env_mock)
        # 2- koji download (handled by env_mock)
        # 3- restorecon (handled by rc_mock)
        self.assertEqual(env_mock.call_count, 2)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(env_mock.call_args_list, expected)

    def test_build_package_brew(self, ld_mock, env_mock, rc_mock):
        self.config.koji_exe = 'brew'
        driver = KojiBuildDriver(cfg_options=self.config)
        driver.build_package(output_directory=self.temp_dir)

        expected = [mock.call(['brew',
                               '--principal', self.config.koji_krb_principal,
                               '--keytab', self.config.koji_krb_keytab,
                               'build', '--wait',
                               self.config.koji_build_target,
                               '%s/python-pysaml2-3.0-1a.el7.centos.src.rpm' %
                               self.temp_dir],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              scratch=True,
                              _cwd=self.temp_dir,
                              _env=mock.ANY),
                    mock.call(['brew', 'download-task', '--logs', '1234'],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              _cwd=self.temp_dir,
                              _env=mock.ANY)]
        # 1- koji build (handled by env_mock)
        # 2- koji download (handled by env_mock)
        # 3- restorecon (handled by rc_mock)
        self.assertEqual(env_mock.call_count, 2)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(env_mock.call_args_list, expected)

    def test_build_package_nokrb(self, ld_mock, env_mock, rc_mock):
        self.config.koji_krb_principal = None
        self.config.koji_krb_keytab = None
        driver = KojiBuildDriver(cfg_options=self.config)
        driver.build_package(output_directory=self.temp_dir)

        expected = [mock.call(['koji',
                               'build', '--wait',
                               self.config.koji_build_target,
                               '%s/python-pysaml2-3.0-1a.el7.centos.src.rpm' %
                               self.temp_dir],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              scratch=True,
                              _cwd=self.temp_dir,
                              _env=mock.ANY),
                    mock.call(['koji', 'download-task', '--logs', '1234'],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              _cwd=self.temp_dir,
                              _env=mock.ANY)]
        # 1- koji build (handled by env_mock)
        # 2- koji download (handled by env_mock)
        # 3- restorecon (handled by rc_mock)
        self.assertEqual(env_mock.call_count, 2)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(env_mock.call_args_list, expected)

    @mock.patch('sh.git', create=True)
    @mock.patch('os.rename')
    @mock.patch('sh.rhpkg', create=True)
    @mock.patch('dlrn.drivers.kojidriver.time', side_effect=_mocked_time)
    @mock.patch('sh.kinit', create=True)
    def test_build_package_rhpkg(self, ki_mock, tm_mock, rhpkg_mock, rn_mock,
                                 git_mock, ld_mock, env_mock, rc_mock):
        git_mock.bake().log.side_effect = _mocked_call
        self.config.koji_use_rhpkg = True
        commit = db.Commit(dt_commit=123, project_name='python-pysaml2',
                           commit_hash='1234567890abcdef',
                           distro_hash='1234567890abcdef',
                           extended_hash='1234567890abcdef',
                           dt_distro=123,
                           dt_extended=123)

        driver = KojiBuildDriver(cfg_options=self.config)
        driver.build_package(output_directory=self.temp_dir,
                             package_name='python-pysaml2',
                             commit=commit)

        expected_env = [mock.call(['koji', 'download-task', '--logs', '5678'],
                                  _err=driver._process_koji_output,
                                  _out=driver._process_koji_output,
                                  _cwd=self.rhpkg_extra_dir,
                                  _env=mock.ANY)]

        pkg_date = strftime("%Y-%m-%d-%H%M%S", localtime(_mocked_time()))
        expected_rhpkg = [mock.call.rhpkg('import',
                                          '--skip-diff',
                                          '%s/python-pysaml2-3.0-1a'
                                          '.el7.centos.src'
                                          '.rpm' % self.temp_dir),
                          mock.call.rhpkg('commit', '-p',
                                          '-m',
                                          'DLRN build at %s\n\n'
                                          'Source SHA: 1234567890abcdef\n'
                                          'Dist SHA: 1234567890abcdef\n'
                                          'NVR: python-pysaml2-3.0-1a'
                                          '.el7.centos\n' %
                                          pkg_date),
                          mock.call.rhpkg('build',
                                          '--skip-nvr-check', scratch=True)]
        expected_git = [mock.call.log('--pretty=format:%H %ct',
                                      '-1', '.')]

        # 1- kinit (handled by kb_mock)
        # 2- rhpkg import (handled by rhpkg_mock)
        # 3- rhpkg commit (handled by rhpkg_mock)
        # 4- git log (handled by git_mock)
        # 5- rename (handled by rn_mock)
        # 5- rhpkg build (handled by rhpkg_mock)
        # 6- koji download (handled by env_mock)
        # 7- restorecon (handled by rc_mock)
        self.assertEqual(ki_mock.call_count, 1)
        # Checks the execution of commit, import and build
        self.assertEqual(len(rhpkg_mock.bake().call_args_list), 3)
        # Checks the execution of log and bake
        self.assertEqual(len(git_mock.bake().log.call_args_list), 1)
        self.assertEqual(env_mock.call_count, 1)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(rn_mock.call_count, 1)
        self.assertEqual(env_mock.call_args_list, expected_env)
        self.assertEqual(rhpkg_mock.bake().call_args_list, expected_rhpkg)
        self.assertEqual(git_mock.bake().log.call_args_list, expected_git)

    @mock.patch('sh.git', create=True)
    @mock.patch('os.rename')
    @mock.patch('sh.rhpkg', create=True)
    @mock.patch('dlrn.drivers.kojidriver.time', side_effect=_mocked_time)
    @mock.patch('sh.kinit', create=True)
    def test_build_package_rhpkg_longexthash(self, ki_mock, tm_mock,
                                             rhpkg_mock, rn_mock,
                                             git_mock, ld_mock,
                                             env_mock, rc_mock):
        git_mock.bake().log.side_effect = _mocked_call
        self.config.koji_use_rhpkg = True
        commit = db.Commit(dt_commit=123, project_name='python-pysaml2',
                           commit_hash='1234567890abcdef',
                           distro_hash='fedcba0987654321',
                           extended_hash='123456789012345678901234567890'
                                         '1234567890_abcdefghijabcdefghij'
                                         'abcdefghijabcdefghij',
                           dt_distro=123,
                           dt_extended=123)

        driver = KojiBuildDriver(cfg_options=self.config)
        driver.build_package(output_directory=self.temp_dir,
                             package_name='python-pysaml2',
                             commit=commit)

        expected_env = [mock.call(['koji', 'download-task', '--logs', '5678'],
                                  _err=driver._process_koji_output,
                                  _out=driver._process_koji_output,
                                  _cwd=self.rhpkg_extra_dir_2,
                                  _env=mock.ANY)]

        pkg_date = strftime("%Y-%m-%d-%H%M%S", localtime(_mocked_time()))
        expected_rhpkg = [mock.call.bake()('import',
                                           '--skip-diff',
                                           '%s/python-pysaml2-3.0-1a.el7'
                                           '.centos.src'
                                           '.rpm' % self.temp_dir),
                          mock.call.bake()('commit', '-p',
                                           '-m',
                                           'DLRN build at %s\n\n'
                                           'Source SHA: 1234567890abcdef\n'
                                           'Dist SHA: fedcba0987654321\n'
                                           'NVR: python-pysaml2-3.0-1a'
                                           '.el7.centos\n' %
                                           pkg_date),
                          mock.call.bake()('build',
                                           '--skip-nvr-check', scratch=True)]
        expected_git = [mock.call.bake().log('--pretty=format:%H %ct',
                                             '-1', '.')]

        expected_rn = [mock.call(self.temp_dir, self.rhpkg_extra_dir_2)]
        # 1- kinit (handled by kb_mock)
        # 2- rhpkg import (handled by rhpkg_mock)
        # 3- rhpkg commit (handled by rhpkg_mock)
        # 4- git log (handled by git_mock)
        # 5- rename (handled by rn_mock)
        # 5- rhpkg build (handled by rhpkg_mock)
        # 6- koji download (handled by env_mock)
        # 7- restorecon (handled by rc_mock)
        self.assertEqual(ki_mock.call_count, 1)
        # Checks the execution of commit, import and build
        self.assertEqual(len(rhpkg_mock.bake().call_args_list), 3)
        # Checks the execution of log and bake
        self.assertEqual(len(git_mock.bake().log.call_args_list), 1)
        self.assertEqual(env_mock.call_count, 1)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(rn_mock.call_count, 1)
        self.assertEqual(env_mock.call_args_list, expected_env)
        self.assertEqual(rhpkg_mock.bake().call_args_list, expected_rhpkg)
        self.assertEqual(git_mock.bake().log.call_args_list, expected_git)
        self.assertEqual(rn_mock.call_args_list, expected_rn)

    @mock.patch('sh.git', create=True)
    @mock.patch('os.rename')
    @mock.patch('sh.rhpkg', create=True)
    @mock.patch('dlrn.drivers.kojidriver.time', side_effect=_mocked_time)
    @mock.patch('sh.kinit', create=True)
    def test_build_package_rhpkg_longexthash_ds(self, ki_mock, tm_mock,
                                                rhpkg_mock, rn_mock, git_mock,
                                                ld_mock, env_mock, rc_mock):
        git_mock.bake().log.side_effect = _mocked_call
        self.config.koji_use_rhpkg = True
        self.config.pkginfo_driver = (
            'dlrn.drivers.downstream.DownstreamInfoDriver')
        self.config.use_upstream_spec = False
        commit = db.Commit(dt_commit=123, project_name='python-pysaml2',
                           commit_hash='1234567890abcdef',
                           distro_hash='fedcba0987654321',
                           extended_hash='123456789012345678901234567890'
                                         '1234567890_abcdefghijabcdefghij'
                                         'abcdefghijabcdefghij',
                           dt_distro=123,
                           dt_extended=123)

        driver = KojiBuildDriver(cfg_options=self.config)
        driver.build_package(output_directory=self.temp_dir,
                             package_name='python-pysaml2',
                             commit=commit)

        expected_env = [mock.call(['koji', 'download-task', '--logs', '5678'],
                                  _err=driver._process_koji_output,
                                  _out=driver._process_koji_output,
                                  _cwd=self.rhpkg_extra_dir_3,
                                  _env=mock.ANY)]

        pkg_date = strftime("%Y-%m-%d-%H%M%S", localtime(_mocked_time()))
        expected_rhpkg = [mock.call.bake()('import',
                                           '--skip-diff',
                                           '%s/python-pysaml2-3.0-1a'
                                           '.el7.centos.src'
                                           '.rpm' % self.temp_dir),
                          mock.call.bake()('commit', '-p',
                                           '-m',
                                           'DLRN build at %s\n\n'
                                           'Source SHA: 1234567890abcdef\n'
                                           'Dist SHA: fedcba0987654321\n'
                                           'NVR: python-pysaml2-3.0-1a'
                                           '.el7.centos\n' %
                                           pkg_date),
                          mock.call.bake()('build',
                                           '--skip-nvr-check', scratch=True)]
        expected_git_log = [mock.call.bake().log('--pretty=format:%H %ct',
                                                 '-1', '.'),
                            mock.call.bake().log('--pretty=format:%H %ct',
                                                 '-1', '.')]
        expected_git_pull = [mock.call.bake().pull()]

        expected_rn = [mock.call(self.temp_dir, self.rhpkg_extra_dir_3)]
        # 1- kinit (handled by kb_mock)
        # 2- rhpkg import (handled by rh_mock)
        # 3- rhpkg commit (handled by rh_mock)
        # 4- git log (handled by git_mock)
        # 5- git pull (handled by git_mock)
        # 6- git log (handled by git_mock)
        # 7- rename (handled by rn_mock)
        # 8- rhpkg build (handled by rh_mock)
        # 9- koji download (handled by env_mock)
        # 10- restorecon (handled by rc_mock)
        self.assertEqual(ki_mock.call_count, 1)
        # Checks the three execution of commit, import and build
        self.assertEqual(len(rhpkg_mock.bake().call_args_list), 3)
        # Checks the two execution of log
        self.assertEqual(len(git_mock.bake().log.call_args_list), 2)
        # Checks the execution of pull
        self.assertEqual(len(git_mock.bake().pull.call_args_list), 1)
        self.assertEqual(env_mock.call_count, 1)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(rn_mock.call_count, 1)
        self.assertEqual(env_mock.call_args_list, expected_env)
        self.assertEqual(rhpkg_mock.bake().call_args_list, expected_rhpkg)
        self.assertEqual(git_mock.bake().log.call_args_list, expected_git_log)
        self.assertEqual(git_mock.bake().pull.call_args_list,
                         expected_git_pull)
        self.assertEqual(rn_mock.call_args_list, expected_rn)

    def test_write_mock_config(self, ld_mock, env_mock, rc_mock):
        self.config.koji_build_target = 'foo-target'
        self.config.koji_arch = 'aarch64'
        self.config.fetch_mock_config = True
        self.config.mock_base_packages = 'foo bar'
        driver = KojiBuildDriver(cfg_options=self.config)
        output_file = os.path.join(self.temp_dir, 'dlrn-1.cfg')

        # Create sample downloaded config file
        with open(output_file, "w") as fp:
            fp.write("config_opts['root'] = 'dlrn-centos7-x86_64-1'\n")
            fp.write("config_opts['chroot_setup_cmd'] = 'install abc def\n")
            fp.write("'''")

        expected = "config_opts['chroot_setup_cmd'] = 'install foo bar'\n"

        driver.write_mock_config(output_file)

        with open(output_file, "r") as fp:
            for line in fp.readlines():
                if line.startswith("config_opts['chroot_setup_cmd']"):
                    self.assertEqual(expected, line)

        self.assertEqual(env_mock.call_count, 1)

    def test_write_mock_config_pkg_mgr(self, ld_mock, env_mock, rc_mock):
        self.config.koji_build_target = 'foo-target'
        self.config.koji_arch = 'aarch64'
        self.config.fetch_mock_config = True
        self.config.mock_base_packages = 'foo bar'
        self.config.mock_package_manager = 'apt'
        driver = KojiBuildDriver(cfg_options=self.config)
        output_file = os.path.join(self.temp_dir, 'dlrn-1.cfg')

        # Create sample downloaded config file
        with open(output_file, "w") as fp:
            fp.write("config_opts['root'] = 'dlrn-centos7-x86_64-1'\n")
            fp.write("config_opts['chroot_setup_cmd'] = 'install abc def\n")
            fp.write("'''")

        expected = "config_opts['package_manager'] = 'apt'\n"

        driver.write_mock_config(output_file)

        with open(output_file, "r") as fp:
            for line in fp.readlines():
                if line.startswith("config_opts['package_manager']"):
                    self.assertEqual(expected, line)

        self.assertEqual(env_mock.call_count, 1)

    def test_additional_tags(self, ld_mock, env_mock, rc_mock):
        self.config.koji_add_tags = ['foo', 'bar']
        self.config.koji_exe = 'brew'

        driver = KojiBuildDriver(cfg_options=self.config)
        driver.build_package(output_directory=self.temp_dir)
        expected = [mock.call(['brew',
                               '--principal', self.config.koji_krb_principal,
                               '--keytab', self.config.koji_krb_keytab,
                               'build', '--wait',
                               self.config.koji_build_target,
                               '%s/python-pysaml2-3.0-1a.el7.centos.src.rpm' %
                               self.temp_dir],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              scratch=True,
                              _cwd=self.temp_dir,
                              _env=mock.ANY),
                    mock.call(['brew', 'tag-build', 'foo',
                               'python-pysaml2-3.0-1a.el7.centos'],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              _cwd=self.temp_dir,
                              _env=mock.ANY),
                    mock.call(['brew', 'tag-build', 'bar',
                               'python-pysaml2-3.0-1a.el7.centos'],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              _cwd=self.temp_dir,
                              _env=mock.ANY),
                    mock.call(['brew', 'download-task', '--logs', '1234'],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              _cwd=self.temp_dir,
                              _env=mock.ANY)]
        # 1- koji build (handled by env_mock)
        # 2 and 3- koji tag (handled by env_mock)
        # 4- koji download (handled by env_mock)
        # 5- restorecon (handled by rc_mock)
        self.assertEqual(env_mock.call_count, 4)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(env_mock.call_args_list, expected)

    def test_get_own_task_id(self, ld_mock, env_mock, rc_mock):
        driver = KojiBuildDriver(cfg_options=self.config)
        env_mock.side_effect = _mocked_list_tasks
        driver.exe_name = 'brew'
        driver.config_options.koji_build_target = "rhos-17.0-rhel-9-"\
                                                  "trunk-candidate"
        task_id = driver.get_own_task_id("python-pysaml2-3.0-1a.el7."
                                         "centos.src.rpm")
        self.assertEqual(task_id, "45133830")

    def test_cancel_brew_task(self, ld_mock, env_mock, rc_mock):
        driver = KojiBuildDriver(cfg_options=self.config)
        driver.exe_name = 'brew'
        driver.cancel_brew_task("45133830")
        driver.cancel_brew_task(45133830)
        driver.cancel_brew_task(None)
        self.assertRaises(ValueError, driver.cancel_brew_task, "")
        self.assertRaises(ValueError, driver.cancel_brew_task, "foo")
        # cancel_brew_tasks accepts number
        # in integer or string Built-in types.
        self.assertEqual(env_mock.call_count, 2)

    @mock.patch('sh.git', create=True)
    @mock.patch('dlrn.drivers.kojidriver.KojiBuildDriver.get_own_task_id')
    @mock.patch('dlrn.drivers.kojidriver.KojiBuildDriver.cancel_brew_task')
    @mock.patch('os.rename')
    @mock.patch('sh.rhpkg', create=True)
    @mock.patch('dlrn.drivers.kojidriver.time', side_effect=_mocked_time)
    @mock.patch('sh.kinit', create=True)
    def test_build_package_rhpkg_timeout(self, ki_mock, tm_mock, rhpkg_mock,
                                         rn_mock, cl_mock, gt_mock, git_mock,
                                         ld_mock, env_mock, rc_mock):
        rhpkg_mock.bake().side_effect = _mocked_call_and_timeout
        git_mock.bake().log.side_effect = _mocked_call_and_timeout
        self.config.koji_use_rhpkg = True
        self.config.koji_rhpkg_timeout = -1
        commit = db.Commit(dt_commit=123, project_name='python-pysaml2',
                           commit_hash='1234567890abcdef',
                           distro_hash='1234567890abcdef',
                           extended_hash='1234567890abcdef',
                           dt_distro=123,
                           dt_extended=123)

        driver = KojiBuildDriver(cfg_options=self.config)

        self.assertRaises(sh.TimeoutException, driver.build_package,
                          output_directory=self.temp_dir,
                          package_name='python-pysaml2', commit=commit)
        self.assertEqual(gt_mock.call_count, 1)
        self.assertEqual(cl_mock.call_count, 1)
