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
from dlrn.drivers.kojidriver import KojiBuildDriver
from dlrn.shell import default_options
from dlrn.tests import base
from six.moves import configparser
from time import localtime
from time import strftime

def _mocked_listdir(directory):
    return ['python-pysaml2-3.0-1a.el7.centos.src.rpm']


def _mocked_time():
    return float(1533293385.545039)


@mock.patch('sh.restorecon', create=True)
@mock.patch('sh.env', create=True)
@mock.patch('os.listdir', side_effect=_mocked_listdir)
class TestDriverKoji(base.TestCase):
    def setUp(self):
        super(TestDriverKoji, self).setUp()
        config = configparser.RawConfigParser(default_options)
        config.read("projects.ini")
        self.config = ConfigOptions(config)
        self.config.koji_krb_principal = 'test@example.com'
        self.config.koji_krb_keytab = '/home/test/test.keytab'
        self.config.koji_scratch_build = True
        self.config.koji_build_target = 'build-target'
        self.temp_dir = tempfile.mkdtemp()
        # Create fake build log
        with open("%s/kojibuild.log" % self.temp_dir, 'a') as fp:
            fp.write("Created task: 1234")
        with open("%s/rhpkgbuild.log" % self.temp_dir, 'a') as fp:
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
                              _env={'PATH': '/usr/bin/'}),
                    mock.call(['koji', 'download-task', '--logs', '1234'],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              _cwd=self.temp_dir,
                              _env={'PATH': '/usr/bin/'})]
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
                              _env={'PATH': '/usr/bin/'}),
                    mock.call(['koji', 'download-task', '--logs', '1234'],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              _cwd=self.temp_dir,
                              _env={'PATH': '/usr/bin/'})]
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
                              _env={'PATH': '/usr/bin/'}),
                    mock.call(['brew', 'download-task', '--logs', '1234'],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              _cwd=self.temp_dir,
                              _env={'PATH': '/usr/bin/'})]
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
                              _env={'PATH': '/usr/bin/'}),
                    mock.call(['koji', 'download-task', '--logs', '1234'],
                              _err=driver._process_koji_output,
                              _out=driver._process_koji_output,
                              _cwd=self.temp_dir,
                              _env={'PATH': '/usr/bin/'})]
        # 1- koji build (handled by env_mock)
        # 2- koji download (handled by env_mock)
        # 3- restorecon (handled by rc_mock)
        self.assertEqual(env_mock.call_count, 2)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(env_mock.call_args_list, expected)

    @mock.patch.object(sh.Command, '__call__', autospec=True)
    @mock.patch('dlrn.drivers.kojidriver.time', side_effect=_mocked_time)
    def test_build_package_rhpkg(self, tm_mock, rh_mock, ld_mock,
                                 env_mock, rc_mock):
        self.config.koji_use_rhpkg = True
        driver = KojiBuildDriver(cfg_options=self.config)
        driver.build_package(output_directory=self.temp_dir,
                             package_name='python-pysaml2')

        expected_env = [mock.call(['koji', 'download-task', '--logs', '5678'],
                                  _err=driver._process_koji_output,
                                  _out=driver._process_koji_output,
                                  _cwd=self.temp_dir,
                                  _env={'PATH': '/usr/bin/'})]

        pkg_date = strftime("%Y-%m-%d-%H%M%S", localtime(_mocked_time()))
        expected_rh = [mock.call('%s/rhpkg' % self.temp_dir, 'import',
                                 '--skip-diff',
                                 '%s/python-pysaml2-3.0-1a.el7.centos.src'
                                 '.rpm' % self.temp_dir),
                       mock.call('%s/rhpkg' % self.temp_dir, 'commit', '-p',
                                 '-m',
                                 'DLRN build at 2018-08-03-124945'),
                       mock.call('%s/rhpkg' % self.temp_dir, 'build',
                                 scratch=True)]

        # 1- rhpkg import (handled by rh_mock)
        # 2- rhpkg commit (handled by rh_mock)
        # 3- rhpkg build (handled by rh_mock)
        # 4- koji download (handled by env_mock)
        # 5- restorecon (handled by rc_mock)
        self.assertEqual(rh_mock.call_count, 3)
        self.assertEqual(env_mock.call_count, 1)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(env_mock.call_args_list, expected_env)
        self.assertEqual(rh_mock.call_args_list, expected_rh)
