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
from dlrn.drivers.downstream import DownstreamInfoDriver
from dlrn.tests import base
from six.moves import configparser


def _mocked_versions(*args, **kwargs):
    with open('./dlrn/tests/samples/versions.csv', 'r') as fp:
        output = fp.readlines()
    return output


def _mocked_refreshrepo(*args, **kwargs):
    return 'a', 'b', 'c'


def _mocked_listdir(path):
    return ['openstack-nova.spec']


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
        return '0'
    elif param == 'PATH':
        return '/tmp/fake/path'


@mock.patch('dlrn.drivers.downstream.fetch_remote_file',
            side_effect=_mocked_versions)
class TestDriverDownstream(base.TestCase):
    def setUp(self):
        super(TestDriverDownstream, self).setUp()
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set("DEFAULT", "pkginfo_driver",
                   "dlrn.drivers.downstream.DownstreamInfoDriver")
        self.temp_dir = tempfile.mkdtemp()
        self.config = ConfigOptions(config)
        self.config.versions_url = \
            'https://trunk.rdoproject.org/centos7-master/current/versions.csv'
        self.config.downstream_distro_branch = 'testbranch'
        self.config.downstream_distgit_base = 'git://git.example.com/rpms'
        self.config.downstream_source_git_key = 'ds-patches'
        self.config.downstream_source_git_branch = 'dsbranch'
        self.config.datadir = self.temp_dir
        self.config.use_upstream_spec = False

    def tearDown(self):
        super(TestDriverDownstream, self).tearDown()
        shutil.rmtree(self.temp_dir)

    def test_versions_parse(self, uo_mock):
        driver = DownstreamInfoDriver(cfg_options=self.config)
        versions = driver._getversions()
        nv = versions['openstack-nova']
        assert nv[1] == 'c9de185ea1ac1e8d4435c5863b2ad7cefdb28c76', nv[1]
        assert nv[3] == '118992921c733bc0079e34dbde59cc8b3c1312dc', nv[3]

    @mock.patch('dlrn.drivers.downstream.DownstreamInfoDriver._distgit_setup',
                return_value=True)
    @mock.patch('dlrn.drivers.downstream.refreshrepo',
                side_effect=_mocked_refreshrepo)
    def test_getinfo(self, rr_mock, ds_mock, uo_mock):
        driver = DownstreamInfoDriver(cfg_options=self.config)
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
            'ds-patches': 'git://git.example.com/downstream/nova',
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
            dev_mode=True)

        expected = [mock.call('git://git.example.com/rpms/nova',
                              self.temp_dir + '/openstack-nova_distro',
                              self.config, 'testbranch',
                              full_path=self.temp_dir + '/openstack-nova_'
                                                        'distro/',
                              local=None),
                    mock.call('git://git.example.com/rpms/nova',
                              self.temp_dir + '/openstack-nova_distro_'
                                              'upstream',
                              self.config, 'rpm-master',
                              full_path=self.temp_dir + '/openstack-nova'
                                                        '_distro_upstream/',
                              local=None),
                    mock.call('git://git.openstack.org/openstack/nova',
                              self.temp_dir + '/nova', self.config, 'master',
                              local=None)]
        if len(rr_mock.call_args_list) == 2:
            # first refreshrepo call is skipped in dev_mode when
            # distro_dir already exists
            expected = expected[1:]
        self.assertEqual(rr_mock.call_args_list, expected)
        self.assertEqual(skipped, False)

        pi = pkginfo[0]
        assert pi.commit_hash == 'c9de185ea1ac1e8d4435c5863b2ad7cefdb28c76', \
            pi.commit_hash

    @mock.patch('dlrn.drivers.downstream.refreshrepo',
                side_effect=Exception('Failed to clone git repository'))
    def test_getinfo_exception(self, rr_mock, uo_mock):
        driver = DownstreamInfoDriver(cfg_options=self.config)
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

        self.assertEqual(pkginfo, [])
        self.assertEqual(skipped, True)

    def test_getinfo_notinversions(self, uo_mock):
        self.config.use_components = True
        driver = DownstreamInfoDriver(cfg_options=self.config)
        package = {
            'name': 'openstack-neutron',
            'project': 'neutron',
            'conf': 'rpmfactory-core',
            'upstream': 'git://git.openstack.org/openstack/neutron',
            'patches': 'http://review.rdoproject.org/r/openstack/neutron.git',
            'distgit': 'git://git.example.com/rpms/neutron',
            'master-distgit':
                'git://git.example.com/rpms/neutron',
            'name': 'openstack-neutron',
            'component': 'network',
            'buildsys-tags': []
        }
        pkginfo, skipped = driver.getinfo(
            package=package,
            project='neutron',
            dev_mode=False)

        # Neutron is not in the mocked versions.csv file, so it will be marked
        # as skipped
        self.assertEqual(pkginfo, [])
        self.assertEqual(skipped, True)

    @mock.patch('dlrn.drivers.downstream.DownstreamInfoDriver._distgit_setup',
                return_value=True)
    @mock.patch('dlrn.drivers.downstream.refreshrepo',
                side_effect=_mocked_refreshrepo)
    def test_getinfo_nodevmode(self, rr_mock, ds_mock, uo_mock):
        driver = DownstreamInfoDriver(cfg_options=self.config)
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
            'ds-patches': 'git://git.example.com/downstream/nova',
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

        expected = [mock.call('git://git.example.com/rpms/nova',
                              self.temp_dir + '/openstack-nova_distro',
                              self.config, 'testbranch',
                              full_path=self.temp_dir + '/openstack-nova_'
                                                        'distro/',
                              local=None),
                    mock.call('git://git.example.com/downstream/nova',
                              self.temp_dir + '/openstack-nova_downstream',
                              self.config, 'dsbranch',
                              full_path=self.temp_dir + '/openstack-nova'
                                                        '_downstream',
                              local=None),
                    mock.call('git://git.example.com/rpms/nova',
                              self.temp_dir + '/openstack-nova_distro_'
                                              'upstream',
                              self.config,
                              '118992921c733bc0079e34dbde59cc8b3c1312dc',
                              full_path=self.temp_dir + '/openstack-nova'
                                                        '_distro_upstream/',
                              local=None),
                    mock.call('git://git.openstack.org/openstack/nova',
                              self.temp_dir + '/nova', self.config, 'master',
                              local=None)]
        self.assertEqual(rr_mock.call_args_list, expected)

        pi = pkginfo[0]
        assert pi.commit_hash == 'c9de185ea1ac1e8d4435c5863b2ad7cefdb28c76', \
            pi.commit_hash

    @mock.patch('dlrn.drivers.downstream.DownstreamInfoDriver._distgit_setup',
                return_value=True)
    @mock.patch('dlrn.drivers.downstream.refreshrepo',
                side_effect=_mocked_refreshrepo)
    def test_getinfo_component(self, rr_mock, ds_mock, uo_mock):
        self.config.use_components = True
        driver = DownstreamInfoDriver(cfg_options=self.config)
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
            'ds-patches': 'git://git.example.com/downstream/nova',
            'component': 'compute',
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
            dev_mode=True)

        pi = pkginfo[0]
        assert pi.component == 'compute'

    @mock.patch('dlrn.drivers.downstream.DownstreamInfoDriver._distgit_setup',
                return_value=True)
    @mock.patch('dlrn.drivers.downstream.refreshrepo',
                side_effect=_mocked_refreshrepo)
    def test_getinfo_component_disabled(self, rr_mock, ds_mock, uo_mock):
        self.config.use_components = False
        driver = DownstreamInfoDriver(cfg_options=self.config)
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

            'component': 'compute',
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
            dev_mode=True)

        pi = pkginfo[0]
        assert pi.component is None

    @mock.patch('os.listdir', side_effect=_mocked_listdir)
    def test_use_upstream_spec(self, ld_mock, uo_mock):
        self.config.use_upstream_spec = True
        self.config.downstream_spec_replace_list =\
            ['^%global with_doc.*/%global with_doc 0']

        # Prepare fake upstream spec
        os.mkdir(os.path.join(self.temp_dir,
                              'openstack-nova_distro_upstream'))
        os.mkdir(os.path.join(self.temp_dir, 'openstack-nova_distro'))
        with open(os.path.join(self.temp_dir,
                               'openstack-nova_distro_upstream',
                               'openstack-nova.spec'), 'w') as fp:
            fp.write("%global with_doc 1\n")
            fp.write("foo")

        driver = DownstreamInfoDriver(cfg_options=self.config)
        driver._distgit_setup(package_name='openstack-nova')

        # This checks that the spec file got copied over, and modified with
        # downstream_spec_replace_list
        with open(os.path.join(self.temp_dir, 'openstack-nova_distro',
                  'openstack-nova.spec'), 'r') as fp:
            result = fp.read()
        expected = '%global with_doc 0\nfoo'
        self.assertEqual(result, expected)

    @mock.patch('os.environ.get', side_effect=_mocked_get_environ)
    @mock.patch('sh.env', create=True)
    @mock.patch('os.listdir', side_effect=_mocked_listdir)
    def test_custom_preprocess(self, ld_mock, sh_mock, get_mock, uo_mock):
        self.config.custom_preprocess = ['/bin/true']
        driver = DownstreamInfoDriver(cfg_options=self.config)
        driver.preprocess(package_name='foo')

        expected = [mock.call(
            ['DLRN_PACKAGE_NAME=foo',
             'DLRN_DISTGIT=%s/foo_distro/' % self.temp_dir,
             'DLRN_UPSTREAM_DISTGIT=%s/foo_distro_upstream/' % self.temp_dir,
             'DLRN_SOURCEDIR=%s/foo' % self.temp_dir,
             'DLRN_USER=myuser',
             'DLRN_DATADIR=%s' % self.config.datadir,
             '/bin/true'],
            _cwd='%s/foo_distro/' % self.temp_dir,
            _env={'LANG': 'C',
                  'MOCK_CONFIG': '/tmp/test.cfg',
                  'RELEASE_DATE': '20150102034455',
                  'RELEASE_MINOR': '0',
                  'RELEASE_NUMBERING': '0.date.hash'})]

        self.assertEqual(sh_mock.call_args_list, expected)
        self.assertEqual(sh_mock.call_count, 1)

    @mock.patch('os.environ.get', side_effect=_mocked_get_environ)
    @mock.patch('sh.env', create=True)
    @mock.patch('os.listdir', side_effect=_mocked_listdir)
    def test_custom_preprocess_distroinfo(self, ld_mock, sh_mock, get_mock,
                                          uo_mock):
        self.config.custom_preprocess = ['/bin/true']
        driver = DownstreamInfoDriver(cfg_options=self.config)
        driver.distroinfo_path = '/tmp/test/dsinfo.yml'
        driver.preprocess(package_name='foo')

        expected = [mock.call(
            ['DLRN_PACKAGE_NAME=foo',
             'DLRN_DISTGIT=%s/foo_distro/' % self.temp_dir,
             'DLRN_UPSTREAM_DISTGIT=%s/foo_distro_upstream/' % self.temp_dir,
             'DLRN_DISTROINFO_REPO=/tmp/test/dsinfo.yml',
             'DLRN_SOURCEDIR=%s/foo' % self.temp_dir,
             'DLRN_USER=myuser',
             'DLRN_DATADIR=%s' % self.config.datadir,
             '/bin/true'],
            _cwd='%s/foo_distro/' % self.temp_dir,
            _env={'LANG': 'C',
                  'MOCK_CONFIG': '/tmp/test.cfg',
                  'RELEASE_DATE': '20150102034455',
                  'RELEASE_MINOR': '0',
                  'RELEASE_NUMBERING': '0.date.hash'})]

        self.assertEqual(sh_mock.call_args_list, expected)
        self.assertEqual(sh_mock.call_count, 1)

    @mock.patch('os.environ.get', side_effect=_mocked_get_environ)
    @mock.patch('sh.env', create=True)
    @mock.patch('os.listdir', side_effect=_mocked_listdir)
    @mock.patch('shutil.copy')
    def test_custom_preprocess_upstream_spec(self, cp_mock, ld_mock, sh_mock,
                                             get_mock, uo_mock):
        self.config.custom_preprocess = ['/bin/true']
        self.config.use_upstream_spec = True
        driver = DownstreamInfoDriver(cfg_options=self.config)
        driver.preprocess(package_name='foo')

        expected = [mock.call(
            ['DLRN_PACKAGE_NAME=foo',
             'DLRN_DISTGIT=%s/foo_distro/' % self.temp_dir,
             'DLRN_UPSTREAM_DISTGIT=%s/foo_distro_upstream/' % self.temp_dir,
             'DLRN_SOURCEDIR=%s/foo' % self.temp_dir,
             'DLRN_USER=myuser',
             'DLRN_DATADIR=%s' % self.config.datadir,
             '/bin/true'],
            _cwd='%s/foo_distro/' % self.temp_dir,
            _env={'LANG': 'C',
                  'MOCK_CONFIG': '/tmp/test.cfg',
                  'RELEASE_DATE': '20150102034455',
                  'RELEASE_MINOR': '0',
                  'RELEASE_NUMBERING': '0.date.hash'})]

        self.assertEqual(sh_mock.call_args_list, expected)
        self.assertEqual(sh_mock.call_count, 1)

    @mock.patch('os.environ.get', side_effect=_mocked_get_environ)
    @mock.patch('sh.env', create=True)
    @mock.patch('os.listdir', side_effect=_mocked_listdir)
    @mock.patch('shutil.copy')
    def test_custom_preprocess_upstream_spec_keep_changelog(self, cp_mock,
                                                            ld_mock, sh_mock,
                                                            get_mock, uo_mock):
        self.config.custom_preprocess = ['/bin/true']
        self.config.use_upstream_spec = True
        self.config.keep_changelog = True
        driver = DownstreamInfoDriver(cfg_options=self.config)
        driver.preprocess(package_name='foo')

        expected = [mock.call(
            ['DLRN_PACKAGE_NAME=foo',
             'DLRN_DISTGIT=%s/foo_distro/' % self.temp_dir,
             'DLRN_UPSTREAM_DISTGIT=%s/foo_distro_upstream/' % self.temp_dir,
             'DLRN_SOURCEDIR=%s/foo' % self.temp_dir,
             'DLRN_USER=myuser',
             'DLRN_DATADIR=%s' % self.config.datadir,
             '/bin/true'],
            _cwd='%s/foo_distro/' % self.temp_dir,
            _env={'LANG': 'C',
                  'MOCK_CONFIG': '/tmp/test.cfg',
                  'RELEASE_DATE': '20150102034455',
                  'RELEASE_MINOR': '0',
                  'RELEASE_NUMBERING': '0.date.hash'})]

        self.assertEqual(sh_mock.call_args_list, expected)
        self.assertEqual(sh_mock.call_count, 1)

    @mock.patch('os.listdir', side_effect=_mocked_listdir)
    def test_custom_preprocess_fail_env_var(self, ld_mock, uo_mock):
        self.config.custom_preprocess = ['/bin/true']
        driver = DownstreamInfoDriver(cfg_options=self.config)
        self.assertRaises(RuntimeError, driver.preprocess, package_name='foo')

    @mock.patch('os.environ.get', side_effect=_mocked_get_environ)
    @mock.patch('os.listdir', side_effect=_mocked_listdir)
    def test_custom_preprocess_fail_command(self, ld_mock, uo_mock, get_mock):
        self.config.custom_preprocess = ['/bin/nonexistingcommand']
        driver = DownstreamInfoDriver(cfg_options=self.config)
        self.assertRaisesRegex(RuntimeError, 'env',
                               driver.preprocess,
                               package_name='foo')

    def test_distgit_setup_not_needed_use_upstream(self, uo_mock):
        self.config.use_upstream_spec = True
        upstream = '%s/foo_distro_upstream/' % self.temp_dir
        downstream = '%s/foo_distro/' % self.temp_dir
        os.mkdir(upstream)
        os.mkdir(downstream)
        with open(upstream + "specfile", "w") as fp:
            fp.write("upstream")
        driver = DownstreamInfoDriver(cfg_options=self.config)
        driver._distgit_setup(package_name='foo')
        self.assertEqual(os.listdir(upstream),
                         os.listdir(downstream))

    def test_distgit_setup_not_needed_not_use_upstream(self, uo_mock):
        self.config.use_upstream_spec = False
        downstream = '%s/foo_distro/' % self.temp_dir
        os.mkdir(downstream)
        driver = DownstreamInfoDriver(cfg_options=self.config)
        driver._distgit_setup(package_name='foo')
        self.assertFalse(os.listdir(downstream))

    @mock.patch('sh.renderspec', create=True, side_effect=True)
    def test_distgit_setup_needed(self, sh_render, uo_mock):
        self.config.use_upstream_spec = False
        downstream_folder = '%s/foo_distro/' % self.temp_dir
        os.mkdir(downstream_folder)
        with open(downstream_folder + "specfile.spec.j2", "w") as fp:
            fp.writelines("downstream")
        driver = DownstreamInfoDriver(cfg_options=self.config)
        driver._distgit_setup(package_name='foo')
        self.assertEqual(sh_render.bake.call_count, 1)
