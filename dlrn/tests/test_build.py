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

import dlrn.shell

from dlrn.build import build
from dlrn.build import build_rpm_wrapper
from dlrn.config import ConfigOptions
from dlrn import db
from dlrn.tests import base
from dlrn import utils


class FakePkgInfo(object):
    def preprocess(self, **argv):
        return


dlrn.shell.pkginfo = FakePkgInfo()


@mock.patch.object(sh.Command, '__call__', autospec=True)
class TestBuild(base.TestCase):
    def setUp(self):
        super(TestBuild, self).setUp()
        config = configparser.RawConfigParser({"gerrit": None})
        config.read("projects.ini")
        config.set('DEFAULT', 'datadir', tempfile.mkdtemp())
        config.set('DEFAULT', 'scriptsdir', tempfile.mkdtemp())
        config.set('DEFAULT', 'baseurl', "file://%s" % config.get('DEFAULT',
                                                                  'datadir'))
        self.config = ConfigOptions(config)
        shutil.copyfile(os.path.join("scripts", "centos.cfg"),
                        os.path.join(self.config.scriptsdir, "centos.cfg"))
        with open(os.path.join(self.config.datadir,
                  "delorean-deps.repo"), "w") as fp:
            fp.write("[test]\nname=test\nenabled=0\n")
        self.session = db.getSession(new=True)
        utils.loadYAML(self.session, './dlrn/tests/samples/commits_1.yaml')

    def tearDown(self):
        super(TestBuild, self).tearDown()
        shutil.rmtree(self.config.datadir)
        shutil.rmtree(self.config.scriptsdir)

    def test_build_rpm_wrapper(self, sh_mock):
        commit = db.getCommits(self.session)[-1]
        build_rpm_wrapper(commit, False, False, False, None, True)
        # git and build_rpms has been called
        self.assertEqual(sh_mock.call_count, 2)
        self.assertTrue(os.path.exists(os.path.join(self.config.datadir,
                                                    "dlrn-1.cfg")))

    def test_build(self, sh_mock):
        commit = db.getCommits(self.session)[-1]
        try:
            build(None, commit, None, False, False, False, True)
        except Exception as e:
            self.assertIn("No rpms built for", str(e))
