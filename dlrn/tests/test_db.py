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

from dlrn import db
from dlrn.tests import base
from dlrn import utils


class TestsWithData(base.TestCase):
    def setUp(self):
        super(TestsWithData, self).setUp()
        self.session = db.getSession(new=True)
        utils.loadYAML(self.session, './dlrn/tests/samples/commits_1.yaml')


@mock.patch('sqlalchemy.orm.sessionmaker', autospec=True)
class TestGetSessions(base.TestCase):
    def setUp(self):
        super(TestGetSessions, self).setUp()
        db._sessions = {}

    def test_getsession(self, sm_mock):
        db.getSession()
        self.assertEqual(len(sm_mock.call_args_list), 1)

    @mock.patch('sqlalchemy.create_engine')
    def test_getsessions(self, ce_mock, sm_mock):
        db.getSession()
        db.getSession(url="sqlite:///test.db")
        # The 2nd call shouldn't result in a new session
        db.getSession()
        self.assertEqual(len(sm_mock.call_args_list), 2)
        expected = [mock.call('sqlite://', pool_recycle=300),
                    mock.call('sqlite:///test.db', pool_recycle=300)]
        self.assertEqual(ce_mock.call_args_list, expected)


class TestGetLastProcessedCommit(TestsWithData):
    def test_noretry(self):
        commit = db.getLastProcessedCommit(self.session, 'python-pysaml2')
        self.assertEqual(commit.dt_build, 1444139517)

    def test_withretry(self):
        # In our sample data the most recent of these has status == RETRY
        commit = \
            db.getLastProcessedCommit(self.session, 'python-tripleoclient')
        self.assertEqual(commit.dt_build, 1444033941)

    def test_newproject(self):
        commit = db.getLastProcessedCommit(self.session, 'python-newproject')
        self.assertEqual(commit, None)


class TestGetLastBuiltCommit(TestsWithData):
    def test_noretry(self):
        commit = \
            db.getLastBuiltCommit(self.session, 'python-pysaml2', None)
        self.assertEqual(commit.dt_build, 1444139517)

    def test_withretry(self):
        # In our sample data the most recent of these has status == RETRY
        commit = \
            db.getLastBuiltCommit(self.session, 'python-tripleoclient', None)
        self.assertEqual(commit.dt_build, 1444033941)

    def test_newproject(self):
        commit = \
            db.getLastBuiltCommit(self.session, 'python-newproject', None)
        self.assertEqual(commit, None)


class TestGetCommits(TestsWithData):
    def test_defaults(self):
        commits = db.getCommits(self.session)
        self.assertEqual(commits.count(), 1)
        self.assertEqual(commits.first().id, 7873)

    def test_no_results(self):
        commits = db.getCommits(self.session, project="dummy")
        self.assertEqual(commits.count(), 0)
        self.assertEqual(commits.first(), None)

    def test_last_success(self):
        commits = db.getCommits(self.session, project="python-tripleoclient",
                                with_status="SUCCESS")
        self.assertEqual(commits.count(), 1)
        self.assertEqual(commits.first().id, 7696)

    def test_last_without_retry(self):
        commits = db.getCommits(self.session, project="python-tripleoclient",
                                without_status="RETRY")
        self.assertEqual(commits.count(), 1)
        self.assertEqual(commits.first().id, 7696)

    def test_last_two(self):
        commits = db.getCommits(self.session, project="python-pysaml2",
                                limit=2)
        self.assertEqual(commits.count(), 2)
        self.assertEqual([c.id for c in commits], [7835, 7834])

    def test_first_failed(self):
        commits = db.getCommits(self.session, project="python-pysaml2",
                                with_status="FAILED", order="asc")
        self.assertEqual(commits.count(), 1)
        self.assertEqual(commits.first().id, 5874)

    def test_first_failed_since(self):
        commits = db.getCommits(self.session, project="python-alembic",
                                with_status="FAILED", order="asc",
                                since="1442487440")
        self.assertEqual(commits.count(), 1)
        self.assertEqual(commits.first().id, 6230)


class TestCommit(TestsWithData):
    def test_commit_compare(self):
        commits = db.getCommits(self.session, project="python-tripleoclient")
        self.assertGreater(commits[0], commits[1])
        self.assertLess(commits[1], commits[0])
        self.assertEqual(commits[0], commits[-1])

    def test_commit_getshardedcommitdir(self):
        commit = db.getLastProcessedCommit(self.session, 'python-pysaml2')
        self.assertIn(commit.commit_hash, commit.getshardedcommitdir())
        commit.distro_hash = None
        self.assertIn(commit.commit_hash, commit.getshardedcommitdir())


class TestProject(TestsWithData):
    def test_email(self):
        project = self.session.query(db.Project).first()
        self.assertFalse(project.suppress_email())
        project.sent_email()
        self.assertTrue(project.suppress_email())
