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
import shutil
import tempfile

from dlrn.config import ConfigOptions
from dlrn.drivers.mockdriver import MockBuildDriver
from dlrn.shell import default_options
from dlrn.tests import base
from six.moves import configparser


def _mocked_listdir(directory):
    return ['python-pysaml2-3.0-1a.el7.centos.src.rpm']


@mock.patch('sh.restorecon', create=True)
@mock.patch('sh.mock', create=True)
@mock.patch('os.listdir', side_effect=_mocked_listdir)
class TestDriverMock(base.TestCase):
    def setUp(self):
        super(TestDriverMock, self).setUp()
        config = configparser.RawConfigParser(default_options)
        config.read("projects.ini")
        self.config = ConfigOptions(config)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        super(TestDriverMock, self).tearDown()
        shutil.rmtree(self.temp_dir)

    def test_build_package(self, ld_mock, mock_mock, rc_mock):
        os.environ['MOCK_CONFIG'] = 'dlrn-1.cfg'
        if os.environ.get('ADDITIONAL_MOCK_OPTIONS'):
            del os.environ['ADDITIONAL_MOCK_OPTIONS']
        driver = MockBuildDriver(cfg_options=self.config)
        driver.build_package(output_directory=self.temp_dir)

        datadir = os.path.realpath(self.config.datadir)
        expected = [mock.call('-v', '-r', '%s/dlrn-1.cfg' % datadir,
                              '--resultdir', self.temp_dir,
                              '--rebuild',
                              '%s/python-pysaml2-3.0-1a.el7.centos.src.rpm' %
                              self.temp_dir,
                              _err=driver._process_mock_output,
                              _out=driver._process_mock_output,
                              postinstall=True)]
        # 2 sh calls:
        # 3- mock (handled by mock_mock)
        # 4- restorecon (handled by rc_mock)
        self.assertEqual(mock_mock.call_count, 1)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(mock_mock.call_args_list, expected)

    def test_build_package_noinstall(self, ld_mock, mock_mock, rc_mock):
        os.environ['MOCK_CONFIG'] = 'dlrn-1.cfg'
        if os.environ.get('ADDITIONAL_MOCK_OPTIONS'):
            del os.environ['ADDITIONAL_MOCK_OPTIONS']
        config_options = self.config
        config_options.install_after_build = False
        driver = MockBuildDriver(cfg_options=config_options)
        driver.build_package(output_directory=self.temp_dir)

        datadir = os.path.realpath(config_options.datadir)
        expected = [mock.call('-v', '-r', '%s/dlrn-1.cfg' % datadir,
                              '--resultdir', self.temp_dir,
                              '--rebuild',
                              '%s/python-pysaml2-3.0-1a.el7.centos.src.rpm' %
                              self.temp_dir,
                              _err=driver._process_mock_output,
                              _out=driver._process_mock_output,
                              postinstall=False)]
        # 2 sh calls:
        # 3- mock (handled by mock_mock)
        # 4- restorecon (handled by rc_mock)
        self.assertEqual(mock_mock.call_count, 1)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(mock_mock.call_args_list, expected)

    def test_build_additional_mock_options(self, ld_mock, mock_mock, rc_mock):
        os.environ['MOCK_CONFIG'] = 'dlrn-1.cfg'
        os.environ['ADDITIONAL_MOCK_OPTIONS'] = '-D repo_bootstrap 1'
        driver = MockBuildDriver(cfg_options=self.config)
        driver.build_package(output_directory=self.temp_dir)

        datadir = os.path.realpath(self.config.datadir)
        expected = [mock.call('-v', '-r', '%s/dlrn-1.cfg' % datadir,
                              '--resultdir', self.temp_dir,
                              '-D repo_bootstrap 1',
                              '--rebuild',
                              '%s/python-pysaml2-3.0-1a.el7.centos.src.rpm' %
                              self.temp_dir,
                              _err=driver._process_mock_output,
                              _out=driver._process_mock_output,
                              postinstall=True)]
        # 2 sh calls:
        # 3- mock (handled by mock_mock)
        # 4- restorecon (handled by rc_mock)
        self.assertEqual(mock_mock.call_count, 1)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(mock_mock.call_args_list, expected)
