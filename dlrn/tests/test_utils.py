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

import hashlib
import os
import requests_mock
import shutil
import tempfile
import yaml

from dlrn import db
from dlrn.tests import base
from dlrn.tests.test_db import TestsWithData
from dlrn import utils
from mock import call
from mock import MagicMock
from mock import patch
from yaml.loader import SafeLoader


class Testdumpshas2file(TestsWithData):
    def test_noretry(self):
        # SUCCESS
        commit = db.getLastProcessedCommit(self.session, 'python-pysaml2')
        # FAILED
        commit2 = db.getLastProcessedCommit(self.session, 'python-alembic')
        # SUCCESS, RETRY (should be ignored)
        commit3 = \
            db.getLastProcessedCommit(self.session, 'python-tripleoclient')

        mock_fp = MagicMock()
        utils.dumpshas2file(mock_fp, commit, "a", "b", commit.status, 0,
                            None,
                            ['python-saml2-1.0-1.el7.src.rpm'])
        utils.dumpshas2file(mock_fp, commit2, "a", "b", commit2.status, 1,
                            'common',
                            ['python-alembic-1.0-2.el7.src.rpm'])
        utils.dumpshas2file(mock_fp, commit3, "a", "b", commit3.status, 2,
                            'common',
                            ['file1-1.2-3.el7.noarch.rpm',
                             'file2-1.2-3.el7.src.rpm'])
        expected = [
            call.write(u'python-pysaml2,a,3a9326f251b9a4162eb0dfa9f1c924ef47c'
                       '2c55a,b,024e24f0cf4366c2290c22f24e42de714d1addd1'
                       ',SUCCESS,0,None,cafecafe,python-saml2-1.0-1.el7\n'),
            call.write(u'python-alembic,a,459549c9ab7fef91b2dc8986bc0643bb2f6'
                       'ec0c8,b,885e80778edb6cbb8ee4d8909623be8062369a04'
                       ',FAILED,1,common,None,python-alembic-1.0-2.el7\n'),
            call.write(u'python-tripleoclient,a,1da7b10e55abf8c518e8f61ee7966'
                       '188f0405f59,b,0b1ce934e5b2e7d45a448f6555d24036f9aeca51'
                       ',SUCCESS,2,common,None,file2-1.2-3.el7\n')
        ]
        self.assertEqual(mock_fp.mock_calls, expected)


class TestIsKnownError(base.TestCase):
    def setUp(self):
        super(TestIsKnownError, self).setUp()
        self.logfile = tempfile.mkstemp()[1]

    def tearDown(self):
        super(TestIsKnownError, self).tearDown()
        os.unlink(self.logfile)

    def test_isknownerror(self):
        self.assertFalse(utils.isknownerror("/unkownfile"),
                         msg="isknownerror didn't succeed on unknown file")

        with open(self.logfile, "w") as fp:
            fp.write("Error: Nothing to do")
        self.assertTrue(utils.isknownerror(self.logfile),
                        msg="isknownerror didn't find an error")

        with open(self.logfile, "w") as fp:
            fp.write("Success")
        self.assertFalse(utils.isknownerror(self.logfile),
                         msg="isknownerror found unknown error")


class TestAggregateRepo(base.TestCase):
    def setUp(self):
        super(base.TestCase, self).setUp()
        self.db_fd, filepath = tempfile.mkstemp()
        self.session = db.getSession("sqlite:///%s" % filepath)
        utils.loadYAML(self.session,
                       './dlrn/tests/samples/commits_components.yaml')
        self.datadir = tempfile.mkdtemp()
        self.repodir = os.path.join(self.datadir,
                                    'repos/component/tripleo/test1')
        os.makedirs(self.repodir)
        with open(os.path.join(self.repodir, "delorean.repo"), 'w') as fp:
            fp.write("TESTING ONE TWO THREE")

    def tearDown(self):
        super(base.TestCase, self).tearDown()
        shutil.rmtree(self.datadir)
        os.close(self.db_fd)

    def test_aggregate_repo_files(self):
        with open('./dlrn/tests/samples/rdo.yml') as f:
            packages = yaml.load(f, Loader=SafeLoader)['packages']
        result = utils.aggregate_repo_files('test1', self.datadir,
                                            self.session, 'delorean',
                                            packages)
        expected_file = os.path.join(self.datadir, 'repos', 'test1',
                                     'delorean.repo')
        assert os.path.exists(expected_file)
        with open(expected_file, 'r') as fp:
            contents = fp.read()
        assert contents == 'TESTING ONE TWO THREE\n'
        assert result == hashlib.md5(b'TESTING ONE TWO THREE\n').hexdigest()

    def test_aggregate_repo_files_hashed_dir(self):
        with open('./dlrn/tests/samples/rdo.yml') as f:
            packages = yaml.load(f, Loader=SafeLoader)['packages']
        utils.aggregate_repo_files('test1', self.datadir, self.session,
                                   'delorean', packages, hashed_dir=True)
        expected_file = os.path.join(self.datadir, 'repos', 'test1',
                                     'delorean.repo')
        assert os.path.exists(expected_file)
        assert os.path.islink(expected_file)
        with open(expected_file, 'r') as fp:
            contents = fp.read()
        assert contents == 'TESTING ONE TWO THREE\n'


class TestFetchRemoteFile(base.TestCase):
    def setUp(self):
        super(base.TestCase, self).setUp()
        self.file_fd, self.filepath = tempfile.mkstemp()
        with open(self.filepath, 'w') as fp:
            fp.write("Test line 1\n")
            fp.write("Test line 2\n")

    def tearDown(self):
        super(base.TestCase, self).tearDown()
        os.close(self.file_fd)

    def test_fetch_file(self):
        expected_results = ["Test line 1\n", "Test line 2\n"]
        results = utils.fetch_remote_file('file://' + self.filepath)
        assert results == expected_results

    @requests_mock.Mocker()
    def test_fetch_url(self, url):
        expected_results = ["Line1\n", "Line2\n"]
        url.get('http://example.com', text='Line1\nLine2\n')
        results = utils.fetch_remote_file('http://example.com')
        assert results == expected_results


class TestRenameOutputDir(base.TestCase):
    @patch('dlrn.db.Commit.getshardedcommitdir')
    @patch('os.rename')
    def test_rename_output_dir(self, mock_os_rename, mock_commit_dir):
        mock_commit_dir.return_value = 'new_hash'
        commit = db.Commit()
        datadir = 'data'
        output_dir = 'data/repos/old_hash'
        expected_call = [call('data/repos/old_hash', 'data/repos/new_hash')]
        expected_results = 'data/repos/new_hash'
        results = utils.rename_output_dir(datadir, output_dir, commit)
        assert mock_os_rename.call_args_list == expected_call
        assert results == expected_results

    @patch('dlrn.db.Commit.getshardedcommitdir')
    @patch('os.rename')
    def test_rename_same_output_dir(self, mock_os_rename, mock_commit_dir):
        mock_commit_dir.return_value = 'same_hash'
        commit = db.Commit()
        datadir = 'data'
        output_dir = 'data/repos/same_hash'
        expected_call = []
        expected_results = 'data/repos/same_hash'
        results = utils.rename_output_dir(datadir, output_dir, commit)
        assert mock_os_rename.call_args_list == expected_call
        assert results == expected_results


class TestRunExternalPreprocess(base.TestCase):
    @patch('sh.env', create=True)
    def test_all_args_except_user(self, mock_sh):
        os.environ['USER'] = 'myuser'
        os.environ['MOCK_CONFIG'] = '/tmp/mock_config'
        os.environ['RELEASE_DATE'] = '1699903817.0'
        os.environ['RELEASE_NUMBERING'] = '2'
        utils.run_external_preprocess(cmdline='/bin/true',
                                      pkgname='foo_pkgname',
                                      distgit='/tmp/foo_distro',
                                      upstream_distgit='/tmp/foo_us_distro',
                                      distroinfo='foo_distroinfo',
                                      source_dir='/tmp/foo',
                                      commit_hash='foo_commit_hash',
                                      datadir='/tmp',
                                      output_directory='/tmp/output_dir',
                                      versions_csv='foo.csv')
        expected = [call(
            ['DLRN_PACKAGE_NAME=foo_pkgname',
             'DLRN_DISTGIT=/tmp/foo_distro',
             'DLRN_UPSTREAM_DISTGIT=/tmp/foo_us_distro',
             'DLRN_DISTROINFO_REPO=foo_distroinfo',
             'DLRN_SOURCEDIR=/tmp/foo',
             'DLRN_SOURCE_COMMIT=foo_commit_hash',
             'DLRN_USER=myuser',
             'DLRN_DATADIR=/tmp',
             'DLRN_OUTPUT_DIRECTORY=/tmp/output_dir',
             'DLRN_VERSIONS_CSV=foo.csv',
             '/bin/true'],
            _cwd='/tmp/foo_distro',
            _env={'LANG': 'C',
                  'MOCK_CONFIG': '/tmp/mock_config',
                  'RELEASE_DATE': '1699903817.0',
                  'RELEASE_MINOR': '0',
                  'RELEASE_NUMBERING': '2'})]
        self.assertEqual(mock_sh.call_args_list, expected)
