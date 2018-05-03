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
from dlrn.drivers.coprdriver import CoprBuildDriver
from dlrn.shell import default_options
from dlrn.tests import base
from six.moves import configparser


def _mocked_listdir(directory):
    return ['python-pysaml2-3.0-1a.el7.centos.src.rpm']


@mock.patch('sh.restorecon', create=True)
@mock.patch('sh.env', create=True)
@mock.patch('os.listdir', side_effect=_mocked_listdir)
class TestDriverCopr(base.TestCase):
    def setUp(self):
        super(TestDriverCopr, self).setUp()
        config = configparser.RawConfigParser(default_options)
        config.read("projects.ini")
        self.config = ConfigOptions(config)
        self.config.coprid = 'account/repo'
        self.temp_dir = tempfile.mkdtemp()
        # Create fake build and download logs
        with open("%s/coprbuild.log" % self.temp_dir, 'a') as fp:
            fp.write("Created builds: 1234")
        open(os.path.join(self.temp_dir, 'coprdownload.log'), 'a').write('')
        # Create fake download file structures
        target_chroot = os.path.join(self.temp_dir, 'fedora-rawhide-i386')
        os.mkdir(target_chroot)
        open(os.path.join(target_chroot, 'state.log.gz'), 'a').write('')
        open(os.path.join(target_chroot, 'pkg.rpm'), 'a').write('')

    def tearDown(self):
        super(TestDriverCopr, self).tearDown()
        shutil.rmtree(self.temp_dir)

    def test_build_package(self, ld_mock, env_mock, rc_mock):
        driver = CoprBuildDriver(cfg_options=self.config)
        driver.build_package(output_directory=self.temp_dir)

        expected = [mock.call(['copr', 'build',
                               self.config.coprid,
                               '%s/python-pysaml2-3.0-1a.el7.centos.src.rpm' %
                               self.temp_dir],
                              _err=driver._process_copr_output,
                              _out=driver._process_copr_output,
                              _cwd=self.temp_dir,
                              _env={'PATH': '/usr/bin/'}),
                    mock.call(['copr', 'download-build', '-d',
                               '%s/1234' % self.temp_dir, '1234'],
                              _err=driver._process_copr_output,
                              _out=driver._process_copr_output,
                              _cwd=self.temp_dir,
                              _env={'PATH': '/usr/bin/'})]
        # 1- copr build (handled by env_mock)
        # 2- copr download-build (handled by env_mock)
        # 3- restorecon (handled by rc_mock)
        self.assertEqual(env_mock.call_count, 2)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertEqual(env_mock.call_args_list, expected)

        # Make sure output_dir is as expected
        content = os.listdir(self.temp_dir)
        self.assertIn('coprdownload.log', content)
        self.assertIn('state.log.gz', content)
        self.assertIn('pkg.rpm', content)
        self.assertNotIn('fedora-rawhide-i386', content)
