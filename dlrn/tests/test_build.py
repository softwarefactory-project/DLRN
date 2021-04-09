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


def mocked_listdir(directory):
    return ['python-pysaml2-3.0-1a.el7.centos.src.rpm']


@mock.patch('sh.restorecon', create=True)
@mock.patch('sh.env', create=True)
@mock.patch.object(sh.Command, '__call__', autospec=True)
class TestBuild(base.TestCase):
    def setUp(self):
        super(TestBuild, self).setUp()
        self.configfile = configparser.RawConfigParser()
        self.configfile.read("projects.ini")
        self.configfile.set('DEFAULT', 'datadir', tempfile.mkdtemp())
        self.configfile.set('DEFAULT', 'scriptsdir', tempfile.mkdtemp())
        self.configfile.set('DEFAULT', 'baseurl', "file://%s" %
                            self.configfile.get('DEFAULT', 'datadir'))
        self.config = ConfigOptions(self.configfile)
        shutil.copyfile(os.path.join("scripts", "centos8.cfg"),
                        os.path.join(self.config.scriptsdir, "centos8.cfg"))
        with open(os.path.join(self.config.datadir,
                  "delorean-deps.repo"), "w") as fp:
            fp.write("[test]\nname=test\nenabled=0\n")
        self.db_fd, filepath = tempfile.mkstemp()
        self.session = db.getSession("sqlite:///%s" % filepath)
        utils.loadYAML(self.session, './dlrn/tests/samples/commits_1.yaml')

    def tearDown(self):
        super(TestBuild, self).tearDown()
        shutil.rmtree(self.config.datadir)
        shutil.rmtree(self.config.scriptsdir)
        os.close(self.db_fd)
        # Make sure env vars are cleaned up
        if 'RELEASE_NUMBERING' in os.environ:
            del os.environ['RELEASE_NUMBERING']
        if 'RELEASE_MINOR' in os.environ:
            del os.environ['RELEASE_MINOR']

    @mock.patch('os.listdir', side_effect=mocked_listdir)
    def test_build_rpm_wrapper(self, ld_mock, sh_mock, env_mock, rc_mock):
        self.configfile.set('DEFAULT', 'build_driver',
                            'dlrn.drivers.mockdriver.MockBuildDriver')
        self.config = ConfigOptions(self.configfile)
        commit = db.getCommits(self.session)[-1]
        build_rpm_wrapper(commit, False, False, False, None, True)
        # 3 sh calls:
        # 1- build_srpm.sh
        # 2- mock (handled by env_mock)
        # 3- restorecon (handled by rc_mock)
        self.assertEqual(env_mock.call_count, 2)
        self.assertEqual(rc_mock.call_count, 1)
        self.assertTrue(os.path.exists(os.path.join(self.config.datadir,
                                                    "dlrn-1.cfg")))

    @mock.patch('dlrn.build.urlopen')
    @mock.patch('os.listdir', side_effect=mocked_listdir)
    def test_build_rpm_wrapper_custom_deps_url(self, ld_mock, url_mock,
                                               sh_mock, env_mock, rc_mock):
        self.configfile.set('DEFAULT', 'build_driver',
                            'dlrn.drivers.mockdriver.MockBuildDriver')
        self.configfile.set('DEFAULT', 'deps_url',
                            'file://%s/custom-deps.repo' %
                            self.configfile.get('DEFAULT', 'datadir'))
        self.config = ConfigOptions(self.configfile)
        commit = db.getCommits(self.session)[-1]
        build_rpm_wrapper(commit, False, False, False, None, True)
        expected = [mock.call('file://%s/custom-deps.repo' %
                              self.configfile.get('DEFAULT', 'datadir'))]
        self.assertEqual(expected, url_mock.call_args_list)

    @mock.patch('dlrn.build.urlopen')
    @mock.patch('os.listdir', side_effect=mocked_listdir)
    def test_build_rpm_wrapper_default_deps_url(self, ld_mock, url_mock,
                                                sh_mock, env_mock, rc_mock):
        self.configfile.set('DEFAULT', 'build_driver',
                            'dlrn.drivers.mockdriver.MockBuildDriver')
        self.config = ConfigOptions(self.configfile)
        commit = db.getCommits(self.session)[-1]
        build_rpm_wrapper(commit, False, False, False, None, True)
        expected = [mock.call('file://%s/delorean-deps.repo' %
                              self.configfile.get('DEFAULT', 'datadir'))]
        self.assertEqual(expected, url_mock.call_args_list)

    @mock.patch('os.listdir', side_effect=mocked_listdir)
    def test_build_rpm_wrapper_release_numbering(self, ld_mock, sh_mock,
                                                 env_mock, rc_mock):
        self.configfile.set('DEFAULT', 'build_driver',
                            'dlrn.drivers.mockdriver.MockBuildDriver')
        self.configfile.set('DEFAULT', 'release_numbering',
                            'minor.date.hash')
        self.configfile.set('DEFAULT', 'release_minor',
                            '2')
        self.config = ConfigOptions(self.configfile)
        commit = db.getCommits(self.session)[-1]
        build_rpm_wrapper(commit, False, False, False, None, True)
        self.assertEqual(os.environ['RELEASE_NUMBERING'], 'minor.date.hash')
        self.assertEqual(os.environ['RELEASE_MINOR'], '2')

    @mock.patch('os.listdir', side_effect=mocked_listdir)
    def test_build(self, ld_mock, sh_mock, env_mock, rc_mock):
        self.configfile.set('DEFAULT', 'build_driver',
                            'dlrn.drivers.mockdriver.MockBuildDriver')
        self.config = ConfigOptions(self.configfile)
        commit = db.getCommits(self.session)[-1]
        try:
            build([], commit, None, False, False, False, True)
        except Exception as e:
            self.assertIn("No rpms built for", str(e))

    @mock.patch('os.listdir', side_effect=mocked_listdir)
    def test_build_configdir(self, ld_mock, sh_mock, env_mock, rc_mock):
        configdir = tempfile.mkdtemp()
        self.configfile.set('DEFAULT', 'configdir', configdir)
        self.configfile.set('DEFAULT', 'build_driver',
                            'dlrn.drivers.mockdriver.MockBuildDriver')
        self.config = ConfigOptions(self.configfile)

        shutil.copyfile(os.path.join("scripts", "centos8.cfg"),
                        os.path.join(configdir, "centos8.cfg"))
        commit = db.getCommits(self.session)[-1]
        expected = [mock.call('%s/centos8.cfg' % configdir,
                              '%s/dlrn-1.cfg.new' % self.config.datadir),
                    mock.call('%s/dlrn-1.cfg.new' % self.config.datadir,
                              '%s/dlrn-1.cfg' % self.config.datadir)]

        with mock.patch('shutil.copyfile',
                        side_effect=shutil.copyfile) as cp_mock:
            build_rpm_wrapper(commit, False, False, False, None, True)
            self.assertEqual(expected, cp_mock.call_args_list)

    @mock.patch('dlrn.drivers.kojidriver.KojiBuildDriver.build_package')
    @mock.patch('os.listdir', side_effect=mocked_listdir)
    @mock.patch('dlrn.drivers.kojidriver.KojiBuildDriver.write_mock_config',
                create=True)
    def test_build_rpm_wrapper_mock_config(self, wm_mock, ld_mock, bp_mock,
                                           sh_mock, env_mock, rc_mock):
        self.configfile.set('kojibuild_driver', 'fetch_mock_config', 'True')
        self.configfile.set('DEFAULT', 'build_driver',
                            'dlrn.drivers.kojidriver.KojiBuildDriver')
        self.config = ConfigOptions(self.configfile)
        commit = db.getCommits(self.session)[-1]
        build_rpm_wrapper(commit, False, False, False, None, True)
        self.assertEqual(wm_mock.call_count, 1)
