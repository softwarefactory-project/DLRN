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
import tempfile

from dlrn.api import app
from dlrn import db
from dlrn.tests import base
from dlrn import utils
from flask import json


def mocked_session(url):
    db_fd, filepath = tempfile.mkstemp()
    session = db.getSession("sqlite:///%s" % filepath)
    utils.loadYAML(session, './dlrn/tests/samples/commits_2.yaml')
    return session


def mocked_getpackages(**kwargs):
    return [{'upstream': 'https://github.com/openstack/python-pysaml2',
             'name': 'python-pysaml2', 'maintainers': 'test@test.com'},
            {'upstream': 'https://github.com/openstack/python-alembic',
             'name': 'python-alembic', 'maintainers': 'test@test.com'},
            {'upstream': 'https://github.com/openstack/puppet-stdlib',
             'name': 'puppet-stdlib', 'maintainers': 'test@test.com'},
            {'upstream': 'https://github.com/openstack/puppet-apache',
             'name': 'puppet-apache', 'maintainers': 'test@test.com'}]


class DLRNAPIGraphQLTestCase(base.TestCase):
    def setUp(self):
        super(DLRNAPIGraphQLTestCase, self).setUp()
        self.db_fd, self.filepath = tempfile.mkstemp()
        app.config['DB_PATH'] = "sqlite:///%s" % self.filepath
        app.config['REPO_PATH'] = '/tmp'
        self.app = app.test_client()
        self.app.testing = True

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.filepath)
        super(DLRNAPIGraphQLTestCase, self).tearDown()


@mock.patch('dlrn.api.graphql.getSession', side_effect=mocked_session)
class TestBasic(DLRNAPIGraphQLTestCase):
    def test_failed_query(self, db_mock):
        response = self.app.get('/api/graphql?query={ foo { id } }')
        self.assertEqual(response.status_code, 400)


@mock.patch('dlrn.api.graphql.getSession', side_effect=mocked_session)
class TestCommitsQuery(DLRNAPIGraphQLTestCase):
    def test_basic_query(self, db_mock):
        response = self.app.get('/api/graphql?query={ commits { id } }')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['commits']), 5)

    def test_filtered_query(self, db_mock):
        query = """
            query {
                commits(projectName: "python-alembic")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['commits']), 2)

    def test_filtered_query_commitHash(self, db_mock):
        query = """
            query {
                commits(commitHash: "1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edc")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['commits']), 1)

    def test_filtered_query_distroHash(self, db_mock):
        query = """
            query {
                commits(distroHash: "008678d7b0e20fbae185f2bb1bd0d9d167586211")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['commits']), 2)

    def test_filtered_query_extendedHash_full(self, db_mock):
        query = """
            query {
                commits(extendedHash: "1234567890_1234567890")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['commits']), 1)

    def test_filtered_query_extendedHash_wildcard(self, db_mock):
        query = """
            query {
                commits(extendedHash: "1234567890_%")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['commits']), 1)

    def test_filtered_query_extendedHash_wildcard_noresult(self, db_mock):
        query = """
            query {
                commits(extendedHash: "abcdef%")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['commits']), 0)

    def test_filtered_query_component(self, db_mock):
        query = """
            query {
                commits(component: "tripleo")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['commits']), 3)

    def test_badfiltered_query(self, db_mock):
        query = """
            query {
                commits(projectFoo: "python-alembic")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 400)

    def test_non_existing_filtered_query(self, db_mock):
        query = """
            query {
                commits(projectName: "python-bar")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['commits']), 0)

    def test_get_multiple_fields(self, db_mock):
        query = """
            query {
                commits(projectName: "puppet-stdlib")
                {
                    status
                    component
                    commitHash
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['commits']), 2)
        self.assertEqual(data['data']['commits'][0]['status'],
                         'SUCCESS')
        self.assertEqual(data['data']['commits'][0]['component'],
                         'tripleo')
        self.assertEqual(data['data']['commits'][0]['commitHash'],
                         '93eee77657978547f5fad1cb8cd30b570da83e68')
        # We are only getting the fields we asked for, and not more
        assert 'distroHash' not in data['data']['commits'][0]

    def test_get_limit(self, db_mock):
        query = """
            query {
                commits(projectName: "python-alembic", limit: 1)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['commits']), 1)

    def test_get_offset(self, db_mock):
        query = """
            query {
                commits(offset: 2)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['commits']), 3)


@mock.patch('dlrn.api.graphql.getSession', side_effect=mocked_session)
class TestcivoteQuery(DLRNAPIGraphQLTestCase):
    def test_basic_query(self, db_mock):
        response = self.app.get('/api/graphql?query={ civote { id } }')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civote']), 5)

    def test_get_offset(self, db_mock):
        query = """
            query {
                civote(offset: 2)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civote']), 3)

    def test_get_limit(self, db_mock):
        query = """
            query {
                civote(limit: 2)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civote']), 2)

    def test_filtered_query(self, db_mock):
        query = """
            query {
                civote(commitId: 5627)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civote']), 2)

    def test_filtered_query_component(self, db_mock):
        query = """
            query {
                civote(ciName: "another-ci")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civote']), 1)

    def test_filtered_query_civote_true(self, db_mock):
        query = """
            query {
                civote(ciVote: true)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civote']), 4)

    def test_filtered_query_civote_false(self, db_mock):
        query = """
            query {
                civote(ciVote: false)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civote']), 1)

    def test_filtered_query_inprogress_true(self, db_mock):
        query = """
            query {
                civote(ciInProgress: true)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civote']), 1)

    def test_filtered_query_inprogress_false(self, db_mock):
        query = """
            query {
                civote(ciInProgress: false)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civote']), 4)

    def test_badfiltered_query(self, db_mock):
        query = """
            query {
                civote(commitId: "TextnotInt")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 400)

    def test_get_multiple_fields(self, db_mock):
        query = """
            query {
                civote(commitId: 5627)
                {
                    commitId
                    ciName
                    ciVote
                    ciInProgress
                    timestamp
                    user
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civote']), 2)
        self.assertEqual(data['data']['civote'][0]['commitId'], 5627)
        self.assertEqual(data['data']['civote'][0]['ciName'],
                         'current-passed-ci')
        self.assertEqual(data['data']['civote'][0]['ciVote'], False)
        self.assertEqual(data['data']['civote'][0]['ciInProgress'], True)
        self.assertEqual(data['data']['civote'][0]['timestamp'], 1441635090)
        self.assertEqual(data['data']['civote'][0]['user'], 'foo')
        assert 'component' not in data['data']['civote'][0]


@mock.patch('dlrn.api.graphql.getSession', side_effect=mocked_session)
class TestCIVoteAggregationQuery(DLRNAPIGraphQLTestCase):
    def test_basic_query(self, db_mock):
        response = self.app.get('/api/graphql?query={ civoteAgg { id } }')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civoteAgg']), 3)

    def test_get_offset(self, db_mock):
        query = """
            query {
                civoteAgg(offset: 2)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civoteAgg']), 1)

    def test_get_limit(self, db_mock):
        query = """
            query {
                civoteAgg(limit: 2)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civoteAgg']), 2)

    def test_filtered_query(self, db_mock):
        query = """
            query {
                civoteAgg(refHash: "12345678")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civoteAgg']), 2)

    def test_filtered_civote_true(self, db_mock):
        query = """
            query {
                civoteAgg(ciVote: true)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civoteAgg']), 2)

    def test_filtered_civote_false(self, db_mock):
        query = """
            query {
                civoteAgg(ciVote: false)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civoteAgg']), 1)

    def test_filtered_ciinprogress_false(self, db_mock):
        query = """
            query {
                civoteAgg(ciInProgress: false)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civoteAgg']), 3)

    def test_filtered_ciinprogress_true(self, db_mock):
        query = """
            query {
                civoteAgg(ciInProgress: true)
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civoteAgg']), 0)

    def test_badfiltered_query(self, db_mock):
        query = """
            query {
                civoteAgg(commit_id: "TextnotInt")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 400)

    def test_get_multiple_fields(self, db_mock):
        query = """
            query {
                civoteAgg(refHash: "12345678")
                {
                    id
                    refHash
                    ciName
                    ciUrl
                    ciVote
                    ciInProgress
                    timestamp
                    notes
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['civoteAgg']), 2)
        self.assertEqual(data['data']['civoteAgg'][0]['refHash'], '12345678')
        self.assertEqual(data['data']['civoteAgg'][0]['ciName'], 'phase2-ci')
        self.assertEqual(data['data']['civoteAgg'][0]['ciUrl'],
                         'http://dummyci.example.com/phase2-ci')
        self.assertEqual(data['data']['civoteAgg'][0]['ciVote'], False)
        self.assertEqual(data['data']['civoteAgg'][0]['ciInProgress'], False)
        self.assertEqual(data['data']['civoteAgg'][0]['timestamp'],
                         1441635195)
        self.assertEqual(data['data']['civoteAgg'][0]['notes'], '')
        assert 'user' not in data['data']['civoteAgg'][0]


@mock.patch('dlrn.drivers.rdoinfo.RdoInfoDriver.getpackages',
            side_effect=mocked_getpackages)
@mock.patch('dlrn.api.graphql.getSession', side_effect=mocked_session)
class TestPackageStatusQuery(DLRNAPIGraphQLTestCase):
    def test_basic_query(self, db_mock, gp_mock):
        response = self.app.get('/api/graphql?query={ packageStatus { id } }')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['packageStatus']), 4)

    def test_filtered_query(self, db_mock, gp_mock):
        query = """
            query {
                packageStatus(projectName: "python-alembic")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['packageStatus']), 1)

    def test_filtered_query_status(self, db_mock, gp_mock):
        query = """
            query {
                packageStatus(status: "NO_BUILD")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['packageStatus']), 1)

    def test_filtered_query_missing(self, db_mock, gp_mock):
        query = """
            query {
                packageStatus(status: "FAILED")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['packageStatus']), 0)

    def test_badfiltered_query(self, db_mock, gp_mock):
        query = """
            query {
                packageStatus(statuserror: "RETRY")
                {
                    id
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        self.assertEqual(response.status_code, 400)

    def test_get_multiple_fields(self, db_mock, gp_mock):
        query = """
            query {
                packageStatus(status: "SUCCESS")
                {
                    id
                    projectName
                    status
                    lastSuccess
                }
            }
        """
        response = self.app.get('/api/graphql?query=%s' % query)
        data = json.loads(response.data)
        self.assertEqual(len(data['data']['packageStatus']), 3)
        self.assertEqual(data['data']['packageStatus'][0]['projectName'],
                         'python-pysaml2')
        self.assertEqual(data['data']['packageStatus'][0]['status'],
                         'SUCCESS')
        self.assertEqual(data['data']['packageStatus'][0]['lastSuccess'], None)
        assert 'firstFailureCommit' not in data['data']['packageStatus'][0]
