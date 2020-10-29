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
        self.assertEqual(len(data['data']['commits']), 4)

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
        self.assertEqual(len(data['data']['commits']), 2)

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
        self.assertEqual(len(data['data']['commits']), 1)
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
        self.assertEqual(len(data['data']['commits']), 2)
