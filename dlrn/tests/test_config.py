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

from dlrn.tests import base
from six.moves import configparser

from dlrn.config import ConfigOptions
from dlrn.config import getConfigOptions
import os


class TestConfigOptions(base.TestCase):
    def setUp(self):
        super(TestConfigOptions, self).setUp()
        self.config = configparser.RawConfigParser()
        self.config.read("projects.ini")

    def test_without_gitrepo_driver(self):
        self.config.remove_section("gitrepo_driver")
        ConfigOptions(self.config)

    def test_with_gitrepo_driver(self):
        self.config.set("DEFAULT", "pkginfo_driver",
                        "dlrn.drivers.gitrepo.GitRepoDriver")
        self.config.set("gitrepo_driver", "skip", "pkg1,pkg2")
        config = ConfigOptions(self.config)
        self.assertEqual(config.skip_dirs, ["pkg1", "pkg2"])

    def test_without_rdoinfo_driver(self):
        self.config.remove_section("rdoinfo_driver")
        ConfigOptions(self.config)

    def test_with_rdoinfo_driver(self):
        self.config.set("DEFAULT", "pkginfo_driver",
                        "dlrn.drivers.rdoinfo.RdoInfoDriver")
        self.config.set(
            "rdoinfo_driver", "repo", "https://test/test.git")
        config = ConfigOptions(self.config)
        self.assertEqual(
            config.rdoinfo_repo, 'https://test/test.git')

    def test_get_config_option(self):
        config = ConfigOptions(self.config)
        self.assertEqual(config, getConfigOptions())

    def test_override(self):
        self.config.set("DEFAULT", "fallback_to_master", "1")
        self.config.set("DEFAULT", "workers", "7")
        config = ConfigOptions(self.config)
        # No changes
        self.assertEqual(config.fallback_to_master, True)
        self.assertEqual(config.workers, 7)

        overrides = ['DEFAULT.fallback_to_master=0',
                     'DEFAULT.workers=3']
        config = ConfigOptions(self.config, overrides=overrides)
        # Overrides in effect
        self.assertEqual(config.fallback_to_master, False)
        self.assertEqual(config.workers, 3)

    def test_override_non_existing(self):
        overrides = ['DEFAULT.non_existing_option=0']
        self.assertRaises(RuntimeError, ConfigOptions,
                          self.config, overrides=overrides)

    def test_dynamic_dirs(self):
        config = ConfigOptions(self.config)
        self.assertEqual(config.scriptsdir, './scripts')
        self.assertEqual(config.configdir, './scripts')
        self.assertEqual(config.templatedir, './dlrn/templates')

    def test_detect_dirs(self):
        self.config = configparser.RawConfigParser()
        self.config.read("samples/projects.ini.detect")
        config = ConfigOptions(self.config)
        self.assertEqual(
            config.datadir,
            os.path.realpath(os.path.join(
                             os.path.dirname(os.path.abspath(__file__)),
                             "../../data")))
        self.assertEqual(
            config.templatedir,
            os.path.realpath(os.path.join(
                             os.path.dirname(os.path.abspath(__file__)),
                             "../templates")))
        self.assertEqual(
            config.scriptsdir,
            os.path.realpath(os.path.join(
                             os.path.dirname(os.path.abspath(__file__)),
                             "../../scripts")))
