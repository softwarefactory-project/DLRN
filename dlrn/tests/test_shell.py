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
import sys
import tempfile

from dlrn.config import ConfigOptions
from dlrn import db
from dlrn import shell
from dlrn.tests import base
from dlrn import utils

from six.moves import configparser


def mocked_session(url):
    session = db.getSession(url)
    utils.loadYAML(session, './dlrn/tests/samples/commits_1.yaml')
    return session


def mocked_session_recheck(url):
    db_fd, filepath = tempfile.mkstemp()
    session = db.getSession("sqlite:///%s" % filepath)
    utils.loadYAML(session, './dlrn/tests/samples/commits_1.yaml')
    return session


def mocked_getpackages(**kwargs):
        return [{'upstream': 'https://github.com/openstack/foo',
                 'name': 'foo', 'maintainers': 'test@test.com'},
                {'upstream': 'https://github.com/openstack/test',
                 'name': 'test', 'maintainers': 'test@test.com'},
                {'upstream': 'https://github.com/openstack/test',
                 'name': 'python-pysaml2', 'maintainers': 'test@test.com'}]


class TestProcessBuildResult(base.TestCase):
    def setUp(self):
        super(TestProcessBuildResult, self).setUp()
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'datadir', tempfile.mkdtemp())
        config.set('DEFAULT', 'scriptsdir', tempfile.mkdtemp())
        config.set('DEFAULT', 'baseurl', "file://%s" % config.get('DEFAULT',
                                                                  'datadir'))
        self.config = ConfigOptions(config)
        self.commit = db.Commit(dt_commit=123, project_name='foo', type="rpm",
                                commit_hash='1c67b1ab8c6fe273d4e175a14f0df5'
                                            'd3cbbd0edf',
                                repo_dir='/home/dlrn/data/foo',
                                distro_hash='c31d1b18eb5ab5aed6721fc4fad06c9'
                                            'bd242490f',
                                dt_distro=123,
                                distgit_dir='/home/dlrn/data/foo_distro',
                                commit_branch='master', dt_build=1441245153)
        self.db_fd, filepath = tempfile.mkstemp()
        self.session = mocked_session("sqlite:///%s" % filepath)
        self.packages = [{'upstream': 'https://github.com/openstack/foo',
                          'name': 'foo', 'maintainers': 'test@test.com'},
                         {'upstream': 'https://github.com/openstack/test',
                          'name': 'test', 'maintainers': 'test@test.com'}]

    def tearDown(self):
        super(TestProcessBuildResult, self).tearDown()
        shutil.rmtree(self.config.datadir)
        shutil.rmtree(self.config.scriptsdir)
        os.close(self.db_fd)

    @mock.patch('os.rename')
    @mock.patch('os.symlink')
    @mock.patch('dlrn.shell.export_commit_yaml')
    @mock.patch('dlrn.shell.genreports')
    @mock.patch('dlrn.shell.sync_repo')
    def test_successful_build(self, rs_mock, gr_mock, ec_mock, sl_mock,
                              rn_mock):
        built_rpms = ['foo-1.2.3.rpm']
        status = [self.commit, built_rpms, 'OK', None]
        output = shell.process_build_result(status, self.packages,
                                            self.session, [])
        self.assertEqual(output, 0)
        self.assertEqual(gr_mock.call_count, 1)
        self.assertEqual(rs_mock.call_count, 1)
        self.assertEqual(ec_mock.call_count, 1)
        self.assertEqual(sl_mock.call_count, 1)
        self.assertEqual(rn_mock.call_count, 1)

    @mock.patch('dlrn.shell.export_commit_yaml')
    @mock.patch('dlrn.shell.sendnotifymail')
    @mock.patch('dlrn.shell.genreports')
    @mock.patch('dlrn.shell.sync_repo')
    def test_failed_build(self, rs_mock, gr_mock, sm_mock, ec_mock):
        error_msg = 'Unit test error'
        status = [self.commit, '', '', error_msg]
        output = shell.process_build_result(status, self.packages,
                                            self.session, [])
        self.assertEqual(output, 1)
        self.assertEqual(gr_mock.call_count, 1)
        self.assertEqual(rs_mock.call_count, 1)
        self.assertEqual(sm_mock.call_count, 1)
        self.assertEqual(ec_mock.call_count, 1)

    @mock.patch('dlrn.shell.submit_review')
    @mock.patch('dlrn.shell.sendnotifymail')
    @mock.patch('dlrn.shell.genreports')
    @mock.patch('dlrn.shell.sync_repo')
    def test_failed_build_gerrit(self, rs_mock, gr_mock, sm_mock, sr_mock):
        self.config.gerrit = 'yes'
        error_msg = 'Unit test error'
        status = [self.commit, '', '', error_msg]
        output = shell.process_build_result(status, self.packages,
                                            self.session, [])
        self.assertEqual(output, 1)
        self.assertEqual(gr_mock.call_count, 1)
        self.assertEqual(rs_mock.call_count, 1)
        self.assertEqual(sm_mock.call_count, 1)
        self.assertEqual(sr_mock.call_count, 1)


@mock.patch('sh.createrepo_c', create=True)
class TestPostBuild(base.TestCase):
    def setUp(self):
        super(TestPostBuild, self).setUp()
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'datadir', tempfile.mkdtemp())
        config.set('DEFAULT', 'scriptsdir', tempfile.mkdtemp())
        config.set('DEFAULT', 'baseurl', "file://%s" % config.get('DEFAULT',
                                                                  'datadir'))
        self.config = ConfigOptions(config)
        self.commit = db.Commit(dt_commit=123, project_name='foo', type="rpm",
                                commit_hash='1c67b1ab8c6fe273d4e175a14f0df5'
                                            'd3cbbd0edf',
                                repo_dir='/home/dlrn/data/foo',
                                distro_hash='c31d1b18eb5ab5aed6721fc4fad06c9'
                                            'bd242490f',
                                dt_distro=123,
                                distgit_dir='/home/dlrn/data/foo_distro',
                                commit_branch='master', dt_build=1441245153)
        self.db_fd, filepath = tempfile.mkstemp()
        self.session = mocked_session("sqlite:///%s" % filepath)
        self.packages = [{'upstream': 'https://github.com/openstack/foo',
                          'name': 'foo', 'maintainers': 'test@test.com',
                          'master-distgit':
                          'https://github.com/rdo-packages/foo-distgit.git'},
                         {'upstream': 'https://github.com/openstack/test',
                          'name': 'test', 'maintainers': 'test@test.com',
                          'master-distgit':
                          'https://github.com/rdo-packages/test-distgit.git'}]

    def tearDown(self):
        super(TestPostBuild, self).tearDown()
        shutil.rmtree(self.config.datadir)
        shutil.rmtree(self.config.scriptsdir)
        os.close(self.db_fd)

    def test_successful_build(self, sh_mock):
        built_rpms = ['repos/1c/67/1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edf'
                      '_c31d1b18/foo-1.2.3.el7.centos.noarch.rpm',
                      'repos/1c/67/1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edf'
                      '_c31d1b18/foo-1.2.3.el7.centos.src.rpm']

        status = [self.commit, built_rpms, 'OK', None]
        # Create directory for the CSV file
        yumdir = os.path.join(self.config.datadir, "repos",
                              self.commit.getshardedcommitdir())
        os.makedirs(yumdir)
        output = shell.post_build(status, self.packages,
                                  self.session)

        self.assertTrue(os.path.exists(
                        os.path.join(self.config.datadir,
                                     "repos",
                                     self.commit.getshardedcommitdir(),
                                     "versions.csv")))

        expected = [mock.call(yumdir)]
        self.assertEqual(sh_mock.call_args_list, expected)
        self.assertEqual(output, 1)     # 1 non-successfully built package

    def test_successful_build_no_failures(self, sh_mock):
        packages = [{'upstream': 'https://github.com/openstack/foo',
                     'name': 'foo', 'maintainers': 'test@test.com',
                     'master-distgit':
                     'https://github.com/rdo-packages/foo-distgit.git'}]
        built_rpms = ['repos/1c/67/1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edf'
                      '_c31d1b18/foo-1.2.3.el7.centos.noarch.rpm',
                      'repos/1c/67/1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edf'
                      '_c31d1b18/foo-1.2.3.el7.centos.src.rpm']

        status = [self.commit, built_rpms, 'OK', None]
        # Create directory for the CSV file
        yumdir = os.path.join(self.config.datadir, "repos",
                              self.commit.getshardedcommitdir())
        os.makedirs(yumdir)
        output = shell.post_build(status, packages, self.session)
        expected = [mock.call(yumdir)]

        self.assertEqual(sh_mock.call_args_list, expected)
        self.assertEqual(output, 0)

    def test_successful_build_no_failures_nosrcrpm(self, sh_mock):
        packages = [{'upstream': 'https://github.com/openstack/foo',
                     'name': 'foo', 'maintainers': 'test@test.com',
                     'master-distgit':
                     'https://github.com/rdo-packages/foo-distgit.git'}]
        built_rpms = ['repos/1c/67/1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edf'
                      '_c31d1b18/foo-1.2.3.el7.centos.noarch.rpm',
                      'repos/1c/67/1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edf'
                      '_c31d1b18/foo-1.2.3.el7.centos.src.rpm']

        self.config.include_srpm_in_repo = False

        status = [self.commit, built_rpms, 'OK', None]
        # Create directory for the CSV file
        yumdir = os.path.join(self.config.datadir, "repos",
                              self.commit.getshardedcommitdir())
        os.makedirs(yumdir)
        output = shell.post_build(status, packages, self.session)
        expected = [mock.call('-x', '*.src.rpm', yumdir)]

        self.assertEqual(sh_mock.call_args_list, expected)
        self.assertEqual(output, 0)

    def test_successful_build_no_repo(self, sh_mock):
        packages = [{'upstream': 'https://github.com/openstack/foo',
                     'name': 'foo', 'maintainers': 'test@test.com',
                     'master-distgit':
                     'https://github.com/rdo-packages/foo-distgit.git'}]
        built_rpms = ['repos/1c/67/1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edf'
                      '_c31d1b18/foo-1.2.3.el7.centos.noarch.rpm',
                      'repos/1c/67/1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edf'
                      '_c31d1b18/foo-1.2.3.el7.centos.src.rpm']

        status = [self.commit, built_rpms, 'OK', None]
        # Create directory for the CSV file
        yumdir = os.path.join(self.config.datadir, "repos",
                              self.commit.getshardedcommitdir())
        os.makedirs(yumdir)
        output = shell.post_build(status, packages, self.session,
                                  build_repo=False)
        # There will be no createrepo call
        expected = []

        self.assertEqual(sh_mock.call_args_list, expected)
        self.assertEqual(output, 0)


class TestRecheck(base.TestCase):
    def setUp(self):
        super(TestRecheck, self).setUp()

    def tearDown(self):
        super(TestRecheck, self).tearDown()

    @mock.patch('dlrn.shell.getSession', side_effect=mocked_session_recheck)
    @mock.patch('dlrn.drivers.rdoinfo.RdoInfoDriver.getpackages',
                side_effect=mocked_getpackages)
    def test_basic_recheck(self, gp_mock, db_mock):
        testargs = ['dlrn', '--package-name',
                    'python-pysaml2', '--recheck']
        with mock.patch.object(sys, 'argv', testargs):
            e = self.assertRaises(SystemExit, shell.main)
            # Rechecking python-pysaml2 should fail because the last commit
            # was successfully built
            self.assertEqual(e.code, 1)

    @mock.patch('dlrn.shell.getSession', side_effect=mocked_session_recheck)
    @mock.patch('dlrn.drivers.rdoinfo.RdoInfoDriver.getpackages',
                side_effect=mocked_getpackages)
    def test_force_recheck_withoutprojectsini(self, gp_mock, db_mock):
        testargs = ['dlrn', '--package-name',
                    'python-pysaml2', '--recheck', '--force-recheck']
        with mock.patch.object(sys, 'argv', testargs):
            e = self.assertRaises(SystemExit, shell.main)
            # Rechecking python-pysaml2 should fail because the last commit
            # was successfully built
            self.assertEqual(e.code, 1)

    @mock.patch('dlrn.shell.getSession', side_effect=mocked_session_recheck)
    @mock.patch('dlrn.drivers.rdoinfo.RdoInfoDriver.getpackages',
                side_effect=mocked_getpackages)
    def test_force_recheck_withprojectsini(self, gp_mock, db_mock):
        testargs = ['dlrn', '--package-name',
                    'python-pysaml2', '--recheck', '--force-recheck',
                    '--config-file',
                    './dlrn/tests/samples/projects_force.ini']
        with mock.patch.object(sys, 'argv', testargs):
            e = self.assertRaises(SystemExit, shell.main)
            # It will work this time
            self.assertEqual(e.code, 0)
