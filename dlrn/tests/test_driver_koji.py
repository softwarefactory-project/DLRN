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
import shutil
import tempfile

from dlrn.config import ConfigOptions
from dlrn.drivers.kojidriver import KojiBuildDriver
from dlrn.tests import base
from six.moves import configparser


def _mocked_listdir(directory):
    return ['python-pysaml2-3.0-1a.el7.centos.src.rpm']


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
        # Create fake build log
        with open("%s/kojibuild.log" % self.temp_dir, 'a') as fp:
            fp.write("Created task: 1234")

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
