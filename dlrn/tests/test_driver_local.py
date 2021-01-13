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
import tempfile

from six.moves import configparser

from dlrn.config import ConfigOptions
from dlrn.drivers.local import LocalDriver
from dlrn.tests import base


class TestDriverLocal(base.TestCase):
    def setUp(self):
        super(TestDriverLocal, self).setUp()
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set("DEFAULT", "pkginfo_driver",
                   "dlrn.drivers.local.LocalDriver")
        self.config = ConfigOptions(config)
        self.config.datadir = tempfile.mkdtemp()
        self.base_dir = tempfile.mkdtemp()

    def tearDown(self):
        super(TestDriverLocal, self).tearDown()
        shutil.rmtree(self.config.datadir)
        shutil.rmtree(self.base_dir)

    @mock.patch.object(sh.Command, '__call__', autospec=True)
    def test_getinfo(self, sh_mock):
        driver = LocalDriver(cfg_options=self.config)
        package = {
            'upstream': 'Unknown', 'name': 'hello-world',
            'master-distgit': '/tmp/hello-world', 'source-branch': '1.0.0'}
        info, skipped = driver.getinfo(
            package=package, project="hello-world")
        self.assertEqual(len(info), 1)
        self.assertEqual(info[0].commit_hash, 'hello-world-1.0.0')
        self.assertEqual(info[0].commit_branch, '1.0.0')
        self.assertEqual(skipped, False)

    def test_getpackages(self):
        package = 'hello-world'
        distgit_dir = os.path.join(self.base_dir, package)
        os.mkdir(distgit_dir)
        os.mkdir(os.path.join(distgit_dir, '.git'))
        with open(os.path.join(distgit_dir, 'hello-world.spec'), 'w') as fp:
            fp.write('Version: 1.0.0')
        # We expect to call DLRN from the local distgit directory
        driver = LocalDriver(cfg_options=self.config)
        packages = driver.getpackages(src_dir=distgit_dir)
        self.assertEqual(len(packages), 1)
        expected_package = {
            'maintainers': 'test@example.com',
            'master-distgit': '%s/hello-world' % self.config.datadir,
            'name': 'hello-world',
            'source-branch': '1.0.0',
            'upstream': 'Unknown'}
        self.assertDictEqual(packages[0], expected_package)
