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

import base64
import mock
import os
import tempfile

from dlrn.api import app
from dlrn import db
from dlrn.tests import base
from dlrn import utils
from flask import json


def mocked_session(url):
    session = db.getSession(new=True)
    utils.loadYAML(session, './dlrn/tests/samples/commits_2.yaml')
    return session


class DLRNAPITestCase(base.TestCase):
    def setUp(self):
        super(DLRNAPITestCase, self).setUp()
        self.db_fd, app.config['DB_PATH'] = tempfile.mkstemp()
        app.config['TESTING'] = '/tmp'
        self.app = app.test_client()
        self.app.testing = True

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(app.config['DB_PATH'])
        super(DLRNAPITestCase, self).tearDown()


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
class TestGetLastTestedRepo(DLRNAPITestCase):
    def test_get_last_tested_repo_needs_json(self, db_mock):
        response = self.app.get('/api/get_last_tested_repo')
        self.assertEqual(response.status_code, 415)

    def test_get_last_tested_repo_no_results(self, db_mock):
        req_data = json.dumps(dict(timestamp='1441635099'))
        response = self.app.get('/api/get_last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_get_last_tested_repo_noconstraints(self, db_mock):
        req_data = json.dumps(dict(timestamp='0'))
        response = self.app.get('/api/get_last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(data['commit_hash'],
                         '1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edc')
        self.assertEqual(data['distro_hash'],
                         '8170b8686c38bafb6021d998e2fb268ab26ccf65')
        self.assertEqual(response.status_code, 200)

    def test_get_last_tested_repo_non_existing_ci(self, db_mock):
        req_data = json.dumps(dict(timestamp='0', link_name='foo'))
        response = self.app.get('/api/get_last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(data['commit_hash'],
                         '1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edc')
        self.assertEqual(data['distro_hash'],
                         '8170b8686c38bafb6021d998e2fb268ab26ccf65')

    def test_get_last_tested_repo_existing_ci(self, db_mock):
        req_data = json.dumps(dict(timestamp='0',
                                   link_name='current-passed-ci'))
        response = self.app.get('/api/get_last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(data['commit_hash'],
                         '17234e9ab9dfab4cf5600f67f1d24db5064f1025')
        self.assertEqual(data['distro_hash'],
                         '024e24f0cf4366c2290c22f24e42de714d1addd1')

    def test_get_last_tested_repo_failed(self, db_mock):
        req_data = json.dumps(dict(timestamp='0', success='0'))
        response = self.app.get('/api/get_last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(data['commit_hash'],
                         '17234e9ab9dfab4cf5600f67f1d24db5064f1025')
        self.assertEqual(data['distro_hash'],
                         '024e24f0cf4366c2290c22f24e42de714d1addd1')


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestGetLastTestedRepoPost(DLRNAPITestCase):
    def test_get_last_tested_repo_needs_auth(self, db2_mock, db_mock):
        response = self.app.post('/api/get_last_tested_repo')
        self.assertEqual(response.status_code, 401)

    def test_get_last_tested_repo_missing_params(self, db2_mock, db_mock):
        req_data = json.dumps(dict(timestamp='0'))
        header = {'Authorization': 'Basic ' + base64.b64encode('foo' +
                  ":" + 'bar')}

        response = self.app.post('/api/get_last_tested_repo',
                                 data=req_data,
                                 headers=header,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_get_last_tested_repo_noconstraints(self, db2_mock, db_mock):
        req_data = json.dumps(dict(timestamp='0',
                                   reporting_link_name='foo-ci'))
        header = {'Authorization': 'Basic ' + base64.b64encode('foo' +
                  ":" + 'bar')}

        response = self.app.post('/api/get_last_tested_repo',
                                 data=req_data,
                                 headers=header,
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(data['commit_hash'],
                         '1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edc')
        self.assertEqual(data['distro_hash'],
                         '8170b8686c38bafb6021d998e2fb268ab26ccf65')
        self.assertEqual(data['in_progress'],
                         True)


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestReportResult(DLRNAPITestCase):
    def test_report_result_needs_auth(self, db2_mock, db_mock):
        response = self.app.post('/api/report_result')
        self.assertEqual(response.status_code, 401)

    def test_report_result_missing_params(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='0'))
        header = {'Authorization': 'Basic ' + base64.b64encode('foo' +
                  ":" + 'bar')}

        response = self.app.post('/api/report_result',
                                 data=req_data,
                                 headers=header,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_report_result_wrong_commit(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='0', link_name='foo-ci', url='',
                                   timestamp='1941635095', success='true',
                                   create_symlink='false',
                                   distro_hash='8170b8686c38bafb6021d998e2fb26'
                                               '8ab26ccf65'))
        header = {'Authorization': 'Basic ' + base64.b64encode('foo' +
                  ":" + 'bar')}

        response = self.app.post('/api/report_result',
                                 data=req_data,
                                 headers=header,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_report_result_successful(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='1c67b1ab8c6fe273d4e'
                                               '175a14f0df5d3cbbd0edc',
                                   link_name='foo-ci', url='',
                                   timestamp='1941635095', success='true',
                                   create_symlink='false',
                                   distro_hash='8170b8686c38bafb6021'
                                               'd998e2fb268ab26ccf65'))
        header = {'Authorization': 'Basic ' + base64.b64encode('foo' +
                  ":" + 'bar')}

        response = self.app.post('/api/report_result',
                                 data=req_data,
                                 headers=header,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 201)
