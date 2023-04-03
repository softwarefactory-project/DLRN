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

from six.moves import configparser

from dlrn.config import ConfigOptions
from dlrn.drivers.gitrepo import GitRepoDriver
from dlrn.tests import base


def _mocked_environ(param, default=None):
    if param == 'USER':
        return 'myuser'
    elif param == 'MOCK_CONFIG':
        return '/tmp/test.cfg'
    elif param == 'RELEASE_DATE':
        return '20150102034455'
    elif param == 'RELEASE_NUMBERING':
        return '0.date.hash'
    elif param == 'RELEASE_MINOR':
        # We are simulating an option where RELEASE_MINOR is not in the env
        return default
    elif param == 'PATH':
        return '/tmp/fake/path'


def _mocked_exists(path):
    return True


class TestDriverGit(base.TestCase):
    def setUp(self):
        super(TestDriverGit, self).setUp()
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set("DEFAULT", "pkginfo_driver",
                   "dlrn.drivers.gitrepo.GitRepoDriver")
        self.config = ConfigOptions(config)
        self.config.datadir = tempfile.mkdtemp()
        self.config.gitrepo_dirs = ['/openstack']

    def tearDown(self):
        super(TestDriverGit, self).tearDown()
        shutil.rmtree(self.config.datadir)

    @mock.patch('sh.renderspec', create=True)
    @mock.patch('sh.git', create=True)
    @mock.patch('dlrn.drivers.gitrepo.refreshrepo')
    def test_getinfo(self, refresh_mock, sh_mock, sh_renderspec):
        refresh_mock.return_value = [None, None, None]
        driver = GitRepoDriver(cfg_options=self.config)
        package = {'upstream': 'test', 'name': 'test'}
        info, skipped = driver.getinfo(package=package,
                                       project="test", dev_mode=True)
        self.assertEqual(info, [])
        self.assertEqual(skipped, False)

    @mock.patch('sh.renderspec', create=True)
    @mock.patch('sh.git', create=True)
    @mock.patch('dlrn.drivers.gitrepo.refreshrepo',
                side_effect=Exception('Failed to clone git repository'))
    def test_getinfo_failure(self, refresh_mock, sh_mock, sh_renderspec):
        refresh_mock.return_value = [None, None, None]
        driver = GitRepoDriver(cfg_options=self.config)
        package = {'upstream': 'test', 'name': 'test'}
        info, skipped = driver.getinfo(package=package,
                                       project="test", dev_mode=True)
        self.assertEqual(info, [])
        self.assertEqual(skipped, True)

    @mock.patch('sh.git', create=True)
    @mock.patch('os.listdir')
    def test_getpackages(self, listdir_mock, sh_mock):
        listdir_mock.return_value = []
        driver = GitRepoDriver(cfg_options=self.config)
        packages = driver.getpackages(dev_mode=True)
        self.assertEqual(packages, [])

    @mock.patch('os.path.exists', side_effect=_mocked_exists)
    @mock.patch('os.environ.get', side_effect=_mocked_environ)
    @mock.patch('sh.renderspec', create=True)
    @mock.patch('sh.env', create=True)
    @mock.patch('os.listdir')
    def test_custom_preprocess(self, ld_mock, env_mock, rs_mock, get_mock,
                               pth_mock):
        self.config.custom_preprocess = ['/bin/true']
        driver = GitRepoDriver(cfg_options=self.config)
        driver.preprocess(package_name='foo')

        directory = '%s/package_info/openstack/foo' % self.config.datadir

        expected = [mock.call(
            ['DLRN_PACKAGE_NAME=foo',
             'DLRN_DISTGIT=%s' % directory,
             'DLRN_SOURCEDIR=%s/foo' % self.config.datadir,
             'DLRN_USER=myuser',
             '/bin/true'],
            _cwd=directory,
            _env={'LANG': 'C',
                  'MOCK_CONFIG': '/tmp/test.cfg',
                  'RELEASE_DATE': '20150102034455',
                  'RELEASE_MINOR': '0',
                  'RELEASE_NUMBERING': '0.date.hash'})]

        self.assertEqual(env_mock.call_args_list, expected)
        self.assertEqual(env_mock.call_count, 1)

    @mock.patch('os.path.exists', side_effect=_mocked_exists)
    @mock.patch('os.environ.get', side_effect=_mocked_environ)
    @mock.patch('sh.renderspec', create=True)
    @mock.patch('sh.env', create=True)
    @mock.patch('os.listdir')
    def test_custom_preprocess_multiple_commands(self, ld_mock, env_mock,
                                                 rs_mock, get_mock, pth_mock):
        self.config.custom_preprocess = ['/bin/true', '/bin/false']
        driver = GitRepoDriver(cfg_options=self.config)
        driver.preprocess(package_name='foo')

        directory = '%s/package_info/openstack/foo' % self.config.datadir

        expected = [mock.call(
            ['DLRN_PACKAGE_NAME=foo',
             'DLRN_DISTGIT=%s' % directory,
             'DLRN_SOURCEDIR=%s/foo' % self.config.datadir,
             'DLRN_USER=myuser',
             '/bin/true'],
            _cwd=directory,
            _env={'LANG': 'C',
                  'MOCK_CONFIG': '/tmp/test.cfg',
                  'RELEASE_DATE': '20150102034455',
                  'RELEASE_MINOR': '0',
                  'RELEASE_NUMBERING': '0.date.hash'}),
            mock.call(
            ['DLRN_PACKAGE_NAME=foo',
             'DLRN_DISTGIT=%s' % directory,
             'DLRN_SOURCEDIR=%s/foo' % self.config.datadir,
             'DLRN_USER=myuser',
             '/bin/false'],
            _cwd=directory,
            _env={'LANG': 'C',
                  'MOCK_CONFIG': '/tmp/test.cfg',
                  'RELEASE_DATE': '20150102034455',
                  'RELEASE_MINOR': '0',
                  'RELEASE_NUMBERING': '0.date.hash'})
            ]

        self.assertEqual(env_mock.call_args_list, expected)
        self.assertEqual(env_mock.call_count, 2)

    @mock.patch('sh.renderspec', create=True)
    @mock.patch('os.listdir')
    def test_custom_preprocess_fail_env_var(self, ld_mock, rs_mock):
        self.config.custom_preprocess = ['/bin/true']
        driver = GitRepoDriver(cfg_options=self.config)
        self.assertRaises(RuntimeError, driver.preprocess, package_name='foo')

    @mock.patch('os.environ.get', side_effect=_mocked_environ)
    @mock.patch('sh.renderspec', create=True)
    @mock.patch('os.listdir')
    def test_custom_preprocess_fail_command(self, ld_mock, rs_mock, get_mock):
        self.config.custom_preprocess = ['/bin/nonexistingcommand']
        driver = GitRepoDriver(cfg_options=self.config)
        self.assertRaisesRegex(RuntimeError, 'env',
                               driver.preprocess,
                               package_name='foo')

    @mock.patch('sh.renderspec', create=True, side_effect=True)
    def test_distgit_setup_needed(self, sh_render):
        driver = GitRepoDriver(cfg_options=self.config)
        driver._distgit_setup(package_name='foo')
        self.assertEqual(sh_render.bake.call_count, 1)
