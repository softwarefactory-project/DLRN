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

from dlrn.config import ConfigOptions
from dlrn.drivers.rdoinfo import RdoInfoDriver
from dlrn.tests import base
from six.moves import configparser


def _mocked_listdir(path):
    return ['foo.spec']


def _mocked_refreshrepo_ok(*args, **kwargs):
    return 'a', 'b', 'c'


def _mocked_git_log(*args, **kwargs):
    return ['1605006232 d2ddfd9c5d7bfea3055ec5d51b4cb11ad12a02f3',
            '1605167482 c7eec96aa361dc52458b9633d781964a6db24e86',
            '1605774411 896f7544a70028ff5db1d5a2d0f3619b62218dd6']


def _mocked_get_environ(param, default=None):
    if param == 'USER':
        return 'myuser'
    elif param == 'MOCK_CONFIG':
        return '/tmp/test.cfg'
    elif param == 'RELEASE_DATE':
        return '20150102034455'
    elif param == 'RELEASE_NUMBERING':
        return '0.date.hash'
    elif param == 'RELEASE_MINOR':
        return '1'


class TestDriverRdoInfo(base.TestCase):
    def setUp(self):
        super(TestDriverRdoInfo, self).setUp()
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set("DEFAULT", "pkginfo_driver",
                   "dlrn.drivers.rdoinfo.RdoInfoDriver")
        self.temp_dir = tempfile.mkdtemp()
        self.config = ConfigOptions(config)
        self.config.datadir = self.temp_dir

    def tearDown(self):
        super(TestDriverRdoInfo, self).tearDown()
        shutil.rmtree(self.temp_dir)

    @mock.patch('distroinfo.info.DistroInfo')
    def test_getpackages_default(self, di_mock):
        driver = RdoInfoDriver(cfg_options=self.config)
        driver.getpackages()
        rdoinfo_repo = ('https://raw.githubusercontent.com/'
                        'redhat-openstack/rdoinfo/master/')

        expected = [mock.call(info_files=['rdo.yml'],
                              remote_info=rdoinfo_repo,
                              cache_base_path=None)]

        self.assertEqual(di_mock.call_args_list, expected)

    @mock.patch('distroinfo.info.DistroInfo')
    def test_getpackages_config(self, di_mock):
        self.config.rdoinfo_file = ['foo.yml']
        self.config.rdoinfo_repo = 'http:/github.com/foo'
        driver = RdoInfoDriver(cfg_options=self.config)
        driver.getpackages()

        expected = [mock.call(info_files=['foo.yml'],
                              remote_git_info='http:/github.com/foo',
                              cache_base_path=None)]

        self.assertEqual(di_mock.call_args_list, expected)

    @mock.patch('distroinfo.info.DistroInfo')
    def test_getpackages_local_info_repo(self, di_mock):
        self.config.rdoinfo_file = ['foo.yml']
        driver = RdoInfoDriver(cfg_options=self.config)
        driver.getpackages(local_info_repo='/tmp/bar')

        expected = [mock.call(info_files=['foo.yml'],
                              local_info='/tmp/bar',
                              cache_base_path=None)]

        self.assertEqual(di_mock.call_args_list, expected)

    @mock.patch('os.environ.get', side_effect=_mocked_get_environ)
    @mock.patch('sh.env', create=True)
    @mock.patch('os.listdir', side_effect=_mocked_listdir)
    def test_custom_preprocess(self, ld_mock, sh_mock, get_mock):
        self.config.custom_preprocess = ['/bin/true']
        driver = RdoInfoDriver(cfg_options=self.config)
        driver.preprocess(package_name='foo')

        expected = [mock.call(['DLRN_PACKAGE_NAME=foo',
                               'DLRN_DISTGIT=%s/foo_distro/' % self.temp_dir,
                               'DLRN_SOURCEDIR=%s/foo' % self.temp_dir,
                               'DLRN_USER=myuser',
                               '/bin/true'],
                              _cwd='%s/foo_distro/' % self.temp_dir,
                              _env={'LANG': 'C',
                                    'MOCK_CONFIG': '/tmp/test.cfg',
                                    'RELEASE_DATE': '20150102034455',
                                    'RELEASE_MINOR': '1',
                                    'RELEASE_NUMBERING': '0.date.hash'})]

        self.assertEqual(sh_mock.call_args_list, expected)
        self.assertEqual(sh_mock.call_count, 1)

    @mock.patch('os.environ.get', side_effect=_mocked_get_environ)
    @mock.patch('sh.env', create=True)
    @mock.patch('os.listdir', side_effect=_mocked_listdir)
    def test_custom_preprocess_source_commit(self, ld_mock, sh_mock,
                                             get_mock):
        self.config.custom_preprocess = ['/bin/true']
        driver = RdoInfoDriver(cfg_options=self.config)
        driver.preprocess(package_name='foo', commit_hash='abc123456')

        expected = [mock.call(['DLRN_PACKAGE_NAME=foo',
                               'DLRN_DISTGIT=%s/foo_distro/' % self.temp_dir,
                               'DLRN_SOURCEDIR=%s/foo' % self.temp_dir,
                               'DLRN_SOURCE_COMMIT=abc123456',
                               'DLRN_USER=myuser',
                               '/bin/true'],
                              _cwd='%s/foo_distro/' % self.temp_dir,
                              _env={'LANG': 'C',
                                    'MOCK_CONFIG': '/tmp/test.cfg',
                                    'RELEASE_DATE': '20150102034455',
                                    'RELEASE_MINOR': '1',
                                    'RELEASE_NUMBERING': '0.date.hash'})]

        self.assertEqual(sh_mock.call_args_list, expected)
        self.assertEqual(sh_mock.call_count, 1)

    @mock.patch('os.environ.get', side_effect=_mocked_get_environ)
    @mock.patch('sh.env', create=True)
    @mock.patch('os.listdir', side_effect=_mocked_listdir)
    def test_custom_preprocess_rdoinfo_repo(self, ld_mock, sh_mock, get_mock):
        self.config.custom_preprocess = ['/bin/true']
        driver = RdoInfoDriver(cfg_options=self.config)
        driver.distroinfo_path = '/tmp/test/rdo.yml'
        driver.preprocess(package_name='foo')

        expected = [mock.call(['DLRN_PACKAGE_NAME=foo',
                               'DLRN_DISTGIT=%s/foo_distro/' % self.temp_dir,
                               'DLRN_DISTROINFO_REPO=/tmp/test/rdo.yml',
                               'DLRN_SOURCEDIR=%s/foo' % self.temp_dir,
                               'DLRN_USER=myuser',
                               '/bin/true'],
                              _cwd='%s/foo_distro/' % self.temp_dir,
                              _env={'LANG': 'C',
                                    'MOCK_CONFIG': '/tmp/test.cfg',
                                    'RELEASE_DATE': '20150102034455',
                                    'RELEASE_MINOR': '1',
                                    'RELEASE_NUMBERING': '0.date.hash'})]

        self.assertEqual(sh_mock.call_args_list, expected)
        self.assertEqual(sh_mock.call_count, 1)

    @mock.patch('sh.env', create=True)
    @mock.patch('os.listdir', side_effect=_mocked_listdir)
    def test_custom_preprocess_multiple_commands(self, ld_mock, sh_mock):
        self.config.custom_preprocess = ['/bin/true', '/bin/true',
                                         '/bin/true']
        driver = RdoInfoDriver(cfg_options=self.config)
        driver.preprocess(package_name='foo')
        self.assertEqual(sh_mock.call_count, 3)

    @mock.patch('os.listdir', side_effect=_mocked_listdir)
    def test_custom_preprocess_fail(self, ld_mock):
        self.config.custom_preprocess = ['/bin/nonexistingcommand']
        driver = RdoInfoDriver(cfg_options=self.config)
        os.mkdir(os.path.join(self.temp_dir, 'foo_distro'))

        self.assertRaises(RuntimeError, driver.preprocess, package_name='foo')

    @mock.patch.object(sh.Command, '__call__', autospec=True,
                       side_effect=_mocked_git_log)
    @mock.patch('dlrn.drivers.rdoinfo.refreshrepo',
                side_effect=_mocked_refreshrepo_ok)
    def test_getinfo_basic(self, rr_mock, git_mock):
        driver = RdoInfoDriver(cfg_options=self.config)
        package = {
            'name': 'openstack-nova',
            'project': 'nova',
            'conf': 'rpmfactory-core',
            'upstream': 'git://git.openstack.org/openstack/nova',
            'patches': 'http://review.rdoproject.org/r/openstack/nova.git',
            'distgit': 'git://git.example.com/rpms/nova',
            'master-distgit':
                'git://git.example.com/rpms/nova',
            'name': 'openstack-nova',
            'buildsys-tags': [
                'cloud7-openstack-pike-release: openstack-nova-16.1.4-1.el7',
                'cloud7-openstack-pike-testing: openstack-nova-16.1.4-1.el7',
                'cloud7-openstack-queens-release: openstack-nova-17.0.5-1.el7',
                'cloud7-openstack-queens-testing: openstack-nova-17.0.5-1.el7',
            ]
        }

        pkginfo, skipped = driver.getinfo(
            package=package,
            project='nova',
            dev_mode=False)

        self.assertEqual(skipped, False)
        self.assertEqual(len(pkginfo), 3)
        pi = pkginfo[0]
        self.assertEqual(pi.commit_hash,
                         'd2ddfd9c5d7bfea3055ec5d51b4cb11ad12a02f3')

    @mock.patch.object(sh.Command, '__call__', autospec=True,
                       side_effect=_mocked_git_log)
    @mock.patch('dlrn.drivers.rdoinfo.refreshrepo',
                side_effect=Exception('Failed to clone git repository'))
    def test_getinfo_git_failure(self, rr_mock, git_mock):
        driver = RdoInfoDriver(cfg_options=self.config)
        package = {
            'name': 'openstack-nova',
            'project': 'nova',
            'conf': 'rpmfactory-core',
            'upstream': 'git://git.openstack.org/openstack/nova',
            'patches': 'http://review.rdoproject.org/r/openstack/nova.git',
            'distgit': 'git://git.example.com/rpms/nova',
            'master-distgit':
                'git://git.example.com/rpms/nova',
            'name': 'openstack-nova',
            'buildsys-tags': [
                'cloud7-openstack-pike-release: openstack-nova-16.1.4-1.el7',
                'cloud7-openstack-pike-testing: openstack-nova-16.1.4-1.el7',
                'cloud7-openstack-queens-release: openstack-nova-17.0.5-1.el7',
                'cloud7-openstack-queens-testing: openstack-nova-17.0.5-1.el7',
            ]
        }

        pkginfo, skipped = driver.getinfo(
            package=package,
            project='nova',
            dev_mode=False)

        self.assertEqual(skipped, True)
        self.assertEqual(pkginfo, [])
