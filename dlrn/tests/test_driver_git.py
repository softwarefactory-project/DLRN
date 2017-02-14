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
import sh
import shutil
import tempfile

from six.moves import configparser

from dlrn.config import ConfigOptions
from dlrn.drivers.gitrepo import GitRepoDriver
from dlrn.tests import base


@mock.patch.object(sh.Command, '__call__', autospec=True)
class TestDriverGit(base.TestCase):
    def setUp(self):
        super(TestDriverGit, self).setUp()
        config = configparser.RawConfigParser({"gerrit": None})
        config.read("projects.ini")
        self.config = ConfigOptions(config)
        self.config.gitrepo_dir = tempfile.mkdtemp()

    def tearDown(self):
        super(TestDriverGit, self).tearDown()
        shutil.rmtree(self.config.gitrepo_dir)

    @mock.patch('dlrn.drivers.gitrepo.refreshrepo')
    def test_getinfo(self, refresh_mock, sh_mock):
        refresh_mock.return_value = [None, None, None]
        driver = GitRepoDriver(cfg_options=self.config)
        package = {'upstream': 'test', 'name': 'test'}
        info = driver.getinfo(package=package, project="test", dev_mode=True)
        self.assertEqual(info, [])

    @mock.patch('os.listdir')
    def test_getpackages(self, listdir_mock, sh_mock):
        listdir_mock.return_value = []
        driver = GitRepoDriver(cfg_options=self.config)
        packages = driver.getpackages(dev_mode=True)
        self.assertEqual(packages, [])
