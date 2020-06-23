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
from mock import call
from mock import MagicMock

import hashlib
import os
import shutil
import tempfile

from dlrn import db
from dlrn.tests import base
from dlrn.tests.test_db import TestsWithData
from dlrn import utils


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
        result = utils.aggregate_repo_files('test1', self.datadir,
                                            self.session, 'delorean')
        expected_file = os.path.join(self.datadir, 'repos', 'test1',
                                     'delorean.repo')
        assert os.path.exists(expected_file)
        with open(expected_file, 'r') as fp:
            contents = fp.read()
        assert contents == 'TESTING ONE TWO THREE\n'
        assert result == hashlib.md5(b'TESTING ONE TWO THREE\n').hexdigest()

    def test_aggregate_repo_files_hashed_dir(self):
        utils.aggregate_repo_files('test1', self.datadir, self.session,
                                   'delorean', hashed_dir=True)
        expected_file = os.path.join(self.datadir, 'repos', 'test1',
                                     'delorean.repo')
        assert os.path.exists(expected_file)
        assert os.path.islink(expected_file)
        with open(expected_file, 'r') as fp:
            contents = fp.read()
        assert contents == 'TESTING ONE TWO THREE\n'
