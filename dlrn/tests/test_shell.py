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
from dlrn import db
from dlrn import shell
from dlrn.tests import base
from dlrn import utils

from six.moves import configparser


def mocked_session(url):
    session = db.getSession(new=True)
    utils.loadYAML(session, './dlrn/tests/samples/commits_1.yaml')
    return session


class TestProcessBuildResult(base.TestCase):
    def setUp(self):
        super(TestProcessBuildResult, self).setUp()
        config = configparser.RawConfigParser({"gerrit": None})
        config.read("projects.ini")
        config.set('DEFAULT', 'datadir', tempfile.mkdtemp())
        config.set('DEFAULT', 'scriptsdir', tempfile.mkdtemp())
        config.set('DEFAULT', 'baseurl', "file://%s" % config.get('DEFAULT',
                                                                  'datadir'))
        self.config = ConfigOptions(config)
        self.commit = db.Commit(dt_commit=123, project_name='foo',
                                commit_hash='1c67b1ab8c6fe273d4e175a14f0df5'
                                            'd3cbbd0edf',
                                repo_dir='/home/dlrn/data/foo',
                                distro_hash='c31d1b18eb5ab5aed6721fc4fad06c9'
                                            'bd242490f',
                                dt_distro=123,
                                distgit_dir='/home/dlrn/data/foo_distro',
                                commit_branch='master')
        self.session = mocked_session('sqlite:///commits.sqlite')
        self.packages = [{'upstream': 'https://github.com/openstack/foo',
                          'name': 'foo', 'maintainers': 'test@test.com'},
                         {'upstream': 'https://github.com/openstack/test',
                          'name': 'test', 'maintainers': 'test@test.com'}]

    def tearDown(self):
        super(TestProcessBuildResult, self).tearDown()
        shutil.rmtree(self.config.datadir)
        shutil.rmtree(self.config.scriptsdir)

    @mock.patch('dlrn.shell.genreports')
    @mock.patch('dlrn.shell.sync_repo')
    def test_successful_build(self, rs_mock, gr_mock):
        built_rpms = 'foo-1.2.3.rpm'
        status = [self.commit, built_rpms, 'OK', None]
        output = shell.process_build_result(status, self.packages,
                                            self.session)
        self.assertEqual(output, 0)
        self.assertEqual(gr_mock.call_count, 1)
        self.assertEqual(rs_mock.call_count, 1)

    @mock.patch('dlrn.shell.sendnotifymail')
    @mock.patch('dlrn.shell.genreports')
    @mock.patch('dlrn.shell.sync_repo')
    def test_failed_build(self, rs_mock, gr_mock, sm_mock):
        error_msg = 'Unit test error'
        status = [self.commit, '', '', error_msg]
        output = shell.process_build_result(status, self.packages,
                                            self.session)
        self.assertEqual(output, 1)
        self.assertEqual(gr_mock.call_count, 1)
        self.assertEqual(rs_mock.call_count, 1)
        self.assertEqual(sm_mock.call_count, 1)

    @mock.patch('dlrn.shell.submit_review')
    @mock.patch('dlrn.shell.sendnotifymail')
    @mock.patch('dlrn.shell.genreports')
    @mock.patch('dlrn.shell.sync_repo')
    def test_failed_build_gerrit(self, rs_mock, gr_mock, sm_mock, sr_mock):
        self.config.gerrit = 'yes'
        error_msg = 'Unit test error'
        status = [self.commit, '', '', error_msg]
        output = shell.process_build_result(status, self.packages,
                                            self.session)
        self.assertEqual(output, 1)
        self.assertEqual(gr_mock.call_count, 1)
        self.assertEqual(rs_mock.call_count, 1)
        self.assertEqual(sm_mock.call_count, 1)
        self.assertEqual(sr_mock.call_count, 1)
