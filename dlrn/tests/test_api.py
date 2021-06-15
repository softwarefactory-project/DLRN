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
import sh
import shutil
import tempfile

from datetime import datetime
from dlrn.api import app
from dlrn.config import ConfigOptions
from dlrn import db
from dlrn.tests import base
from dlrn import utils
from flask import json
from six.moves import configparser
from six.moves.urllib.request import urlopen


def mocked_session(url):
    db_fd, filepath = tempfile.mkstemp()
    session = db.getSession("sqlite:///%s" % filepath)
    utils.loadYAML(session, './dlrn/tests/samples/commits_2.yaml')
    return session


def mocked_urlopen(url):
    if url.startswith('http://example.com'):
        fp = open('./dlrn/tests/samples/commits_remote.yaml', 'rb')
        return fp
    else:
        return urlopen(url)


def mock_opt(config_file):
    cp = configparser.RawConfigParser()
    cp.read(config_file)
    co = ConfigOptions(cp)
    co.use_components = True
    return co


def mock_ag(dirname, datadir, session, reponame, hashed_dir=False):
    return 'abc123'


class DLRNAPITestCase(base.TestCase):
    def setUp(self):
        super(DLRNAPITestCase, self).setUp()
        self.db_fd, self.filepath = tempfile.mkstemp()
        app.config['DB_PATH'] = "sqlite:///%s" % self.filepath
        app.config['REPO_PATH'] = '/tmp'
        self.app = app.test_client()
        self.app.testing = True
        self.headers = {'Authorization': 'Basic %s' % (
            base64.b64encode(b'foo:bar').decode('ascii'))}

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.filepath)
        super(DLRNAPITestCase, self).tearDown()


@mock.patch('dlrn.api.dlrn_api.datetime')
@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
class TestGetLastTestedRepo(DLRNAPITestCase):
    def test_get_last_tested_repo_no_results(self, db_mock, dt_mock):
        req_data = json.dumps(dict(max_age='48'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.get('/api/last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_get_last_tested_repo_no_results_url_params(self, db_mock,
                                                        dt_mock):
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.get('/api/last_tested_repo?max_age=48')
        self.assertEqual(response.status_code, 400)

    def test_get_last_tested_repo_with_age(self, db_mock, dt_mock):
        req_data = json.dumps(dict(max_age='72'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.get('/api/last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        data = json.loads(response.data)

        self.assertEqual(data['commit_hash'],
                         '1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edc')
        self.assertEqual(data['distro_hash'],
                         '8170b8686c38bafb6021d998e2fb268ab26ccf65')
        self.assertEqual(data['job_id'], 'consistent')
        self.assertEqual(data['component'], None)
        self.assertEqual(response.status_code, 200)

    def test_get_last_tested_repo_with_age_url_params(self, db_mock, dt_mock):
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.get('/api/last_tested_repo?max_age=72')
        data = json.loads(response.data)

        self.assertEqual(data['commit_hash'],
                         '1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edc')
        self.assertEqual(data['distro_hash'],
                         '8170b8686c38bafb6021d998e2fb268ab26ccf65')
        self.assertEqual(data['job_id'], 'consistent')
        self.assertEqual(response.status_code, 200)

    def test_get_last_tested_repo_noconstraints(self, db_mock, dt_mock):
        req_data = json.dumps(dict(max_age='0'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.get('/api/last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(data['commit_hash'],
                         '93eee77657978547f5fad1cb8cd30b570da83e68')
        self.assertEqual(data['distro_hash'],
                         '008678d7b0e20fbae185f2bb1bd0d9d167586211')
        self.assertEqual(data['extended_hash'],
                         '1234567890_1234567890')
        self.assertEqual(response.status_code, 200)

    def test_get_last_tested_repo_failed_url_params(self, db_mock, dt_mock):
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.get('/api/last_tested_repo?max_age=0&success=0')
        data = json.loads(response.data)
        self.assertEqual(data['commit_hash'],
                         '17234e9ab9dfab4cf5600f67f1d24db5064f1025')
        self.assertEqual(data['distro_hash'],
                         '024e24f0cf4366c2290c22f24e42de714d1addd1')
        self.assertEqual(data['job_id'], 'current-passed-ci')
        self.assertEqual(response.status_code, 200)

    def test_get_last_tested_repo_sequential(self, db_mock, dt_mock):
        req_data = json.dumps(dict(max_age='0',
                                   job_id='foo-ci',
                                   sequential_mode='true',
                                   previous_job_id='current-passed-ci'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.get('/api/last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(data['commit_hash'],
                         '17234e9ab9dfab4cf5600f67f1d24db5064f1025')
        self.assertEqual(data['distro_hash'],
                         '024e24f0cf4366c2290c22f24e42de714d1addd1')
        self.assertEqual(data['job_id'], 'current-passed-ci')
        self.assertEqual(response.status_code, 200)

    def test_get_last_tested_repo_sequential_needs_previous_job_id(self,
                                                                   db_mock,
                                                                   dt_mock):
        req_data = json.dumps(dict(max_age='0',
                                   job_id='foo-ci',
                                   sequential_mode='true'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.get('/api/last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_get_last_tested_repo_sequential_novote(self, db_mock, dt_mock):
        req_data = json.dumps(dict(max_age='0',
                                   job_id='foo-ci',
                                   sequential_mode='true',
                                   previous_job_id='bar-ci'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.get('/api/last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_get_last_tested_repo_component(self, db_mock, dt_mock):
        req_data = json.dumps(dict(max_age='0', success='1',
                                   component='foo-component'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.get('/api/last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(data['commit_hash'],
                         '1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edc')
        self.assertEqual(data['distro_hash'],
                         '8170b8686c38bafb6021d998e2fb268ab26ccf65')
        self.assertEqual(data['component'], 'foo-component')
        self.assertEqual(response.status_code, 200)


@mock.patch('dlrn.api.dlrn_api.datetime')
@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestPostLastTestedRepo(DLRNAPITestCase):
    def test_post_last_tested_repo_needs_auth(self, db2_mock, db_mock,
                                              dt_mock):
        response = self.app.post('/api/last_tested_repo')
        self.assertEqual(response.status_code, 401)

    def test_post_last_tested_repo_missing_params(self, db2_mock, db_mock,
                                                  dt_mock):
        req_data = json.dumps(dict(max_age='0'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)

        response = self.app.post('/api/last_tested_repo',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_post_last_tested_repo_noconstraints(self, db2_mock, db_mock,
                                                 dt_mock):
        req_data = json.dumps(dict(max_age='0',
                                   reporting_job_id='foo-ci'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)

        response = self.app.post('/api/last_tested_repo',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(data['commit_hash'],
                         '93eee77657978547f5fad1cb8cd30b570da83e68')
        self.assertEqual(data['distro_hash'],
                         '008678d7b0e20fbae185f2bb1bd0d9d167586211')
        self.assertEqual(data['extended_hash'],
                         '1234567890_1234567890')
        self.assertEqual(data['job_id'], 'foo-ci')
        self.assertEqual(data['in_progress'], True)

    def test_post_last_tested_repo_sequential(self, db2_mock, db_mock,
                                              dt_mock):
        req_data = json.dumps(dict(max_age='0',
                                   job_id='foo-ci',
                                   reporting_job_id='foo-ci',
                                   sequential_mode='true',
                                   previous_job_id='current-passed-ci'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.post('/api/last_tested_repo',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(data['commit_hash'],
                         '17234e9ab9dfab4cf5600f67f1d24db5064f1025')
        self.assertEqual(data['distro_hash'],
                         '024e24f0cf4366c2290c22f24e42de714d1addd1')
        self.assertEqual(data['job_id'], 'foo-ci')
        self.assertEqual(data['in_progress'], True)

    def test_post_last_tested_repo_sequential_needs_previous_job_id(self,
                                                                    db2_mock,
                                                                    db_mock,
                                                                    dt_mock):
        req_data = json.dumps(dict(max_age='0',
                                   job_id='foo-ci',
                                   reporting_job_id='foo-ci',
                                   sequential_mode='true'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.post('/api/last_tested_repo',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_post_last_tested_repo_sequential_novote(self, db2_mock, db_mock,
                                                     dt_mock):
        req_data = json.dumps(dict(max_age='0',
                                   job_id='foo-ci',
                                   reporting_job_id='foo-ci',
                                   sequential_mode='true',
                                   previous_job_id='bar-ci'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.post('/api/last_tested_repo',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_post_last_tested_repo_component(self, db2_mock, db_mock,
                                             dt_mock):
        req_data = json.dumps(dict(max_age='0',
                                   reporting_job_id='foo-ci',
                                   component='foo-component'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)

        response = self.app.post('/api/last_tested_repo',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(data['commit_hash'],
                         '1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edc')
        self.assertEqual(data['distro_hash'],
                         '8170b8686c38bafb6021d998e2fb268ab26ccf65')
        self.assertEqual(data['job_id'], 'foo-ci')
        self.assertEqual(data['in_progress'], True)
        self.assertEqual(data['component'], 'foo-component')


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestReportResult(DLRNAPITestCase):
    def test_report_result_needs_auth(self, db2_mock, db_mock):
        response = self.app.post('/api/report_result')
        self.assertEqual(response.status_code, 401)

    def test_report_result_missing_params(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='0'))

        response = self.app.post('/api/report_result',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_report_result_wrong_commit(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='0', job_id='foo-ci', url='',
                                   timestamp='1941635095', success='true',
                                   distro_hash='8170b8686c38bafb6021d998e2fb26'
                                               '8ab26ccf65'))

        response = self.app.post('/api/report_result',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_report_result_no_commit_hash(self, db2_mock, db_mock):
        req_data = json.dumps(dict(distro_hash='0', job_id='foo-ci', url='',
                                   timestamp='1941635095', success='true'))

        response = self.app.post('/api/report_result',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_report_result_no_distro_hash(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='0', job_id='foo-ci', url='',
                                   timestamp='1941635095', success='true'))

        response = self.app.post('/api/report_result',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_report_result_successful(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='1c67b1ab8c6fe273d4e'
                                               '175a14f0df5d3cbbd0edc',
                                   job_id='foo-ci', url='',
                                   timestamp='1941635095', success='true',
                                   distro_hash='8170b8686c38bafb6021'
                                               'd998e2fb268ab26ccf65'))

        response = self.app.post('/api/report_result',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(data['in_progress'], False)
        self.assertEqual(data['success'], True)

    def test_report_result_aggregate(self, db2_mock, db_mock):
        req_data = json.dumps(dict(aggregate_hash='12345678',
                                   job_id='phase2-ci', url='',
                                   timestamp='1941635095', success='true'))

        response = self.app.post('/api/report_result',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(data['in_progress'], False)
        self.assertEqual(data['success'], True)
        self.assertEqual(data['aggregate_hash'], '12345678')

    def test_report_result_agg_and_hash(self, db2_mock, db_mock):
        req_data = json.dumps(dict(aggregate_hash='12345678',
                                   job_id='phase2-ci', url='',
                                   timestamp='1941635095', success='true',
                                   commit_hash='123456'))
        response = self.app.post('/api/report_result',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_report_result_ext_hash(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='93eee77657978547f5fad'
                                               '1cb8cd30b570da83e68',
                                   job_id='foo-ci', url='',
                                   timestamp='1941635095', success='true',
                                   distro_hash='008678d7b0e20fbae185f2'
                                               'bb1bd0d9d167586211',
                                   extended_hash='1234567890_1234567890'))

        response = self.app.post('/api/report_result',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(data['in_progress'], False)
        self.assertEqual(data['success'], True)
        self.assertEqual(data['extended_hash'], '1234567890_1234567890')


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestPromote(DLRNAPITestCase):
    def test_promote_needs_auth(self, db2_mock, db_mock):
        response = self.app.post('/api/promote')
        self.assertEqual(response.status_code, 401)

    def test_promote_missing_commit(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='abc123', distro_hash='abc123',
                                   promote_name='foo'))
        response = self.app.post('/api/promote',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')

        self.assertEqual(response.status_code, 400)

    def test_promote_purged_commit(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='1c67b1ab8c6fe273d4e17'
                                               '5a14f0df5d3cbbd0e77',
                                   distro_hash='8170b8686c38bafb6021d'
                                               '998e2fb268ab26ccf77',
                                   promote_name='foo-ci'))
        response = self.app.post('/api/promote',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 410)
        self.assertEqual(data['message'], 'commit_hash+distro_hash+'
                                          'extended_hash has been'
                                          ' purged, cannot promote it')

    @mock.patch('os.symlink')
    def test_promote_successful(self, sl_mock, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='1c67b1ab8c6fe273d4e'
                                               '175a14f0df5d3cbbd0edc',
                                   distro_hash='8170b8686c38bafb6021'
                                               'd998e2fb268ab26ccf65',
                                   promote_name='foo-ci'))
        response = self.app.post('/api/promote',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')

        expected = [mock.call('1c/67/1c67b1ab8c6fe273d4e175a'
                              '14f0df5d3cbbd0edc_8170b868', '/tmp/foo-ci')]

        self.assertEqual(response.status_code, 201)
        self.assertEqual(sl_mock.call_args_list, expected)
        data = json.loads(response.data)
        self.assertEqual(data['extended_hash'], None)

    @mock.patch('os.symlink')
    def test_promote_successful_exthash(self, sl_mock, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='93eee77657978547f5fad1cb'
                                               '8cd30b570da83e68',
                                   distro_hash='008678d7b0e20fbae185f2bb'
                                               '1bd0d9d167586211',
                                   extended_hash='1234567890_1234567890',
                                   promote_name='my-ci'))
        response = self.app.post('/api/promote',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')

        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['extended_hash'], '1234567890_1234567890')

    def test_promote_invalid_name(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='1c67b1ab8c6fe273d4e'
                                               '175a14f0df5d3cbbd0edc',
                                   distro_hash='8170b8686c38bafb6021'
                                               'd998e2fb268ab26ccf65',
                                   promote_name='consistent'))
        response = self.app.post('/api/promote',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')

        self.assertEqual(response.status_code, 403)

    def test_promote_invalid_name_relative(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='1c67b1ab8c6fe273d4e'
                                               '175a14f0df5d3cbbd0edc',
                                   distro_hash='8170b8686c38bafb6021'
                                               'd998e2fb268ab26ccf65',
                                   promote_name='../consistent'))
        response = self.app.post('/api/promote',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')

        self.assertEqual(response.status_code, 403)


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestPromoteBatch(DLRNAPITestCase):
    def setUp(self):
        super(TestPromoteBatch, self).setUp()
        if os.path.exists('/tmp/component/None'):
            shutil.rmtree('/tmp/component/None')
        if os.path.exists('/tmp/component/tripleo'):
            shutil.rmtree('/tmp/component/tripleo')
        os.makedirs('/tmp/component/None')
        os.makedirs('/tmp/component/tripleo')

    def tearDown(self):
        if os.path.exists('/tmp/component/None'):
            shutil.rmtree('/tmp/component/None')
        if os.path.exists('/tmp/component/tripleo'):
            shutil.rmtree('/tmp/component/tripleo')
        super(TestPromoteBatch, self).tearDown()

    def test_promote_batch_needs_auth(self, db2_mock, db_mock):
        response = self.app.post('/api/promote-batch')
        self.assertEqual(response.status_code, 401)

    def test_promote_batch_missing_commit(self, db2_mock, db_mock):
        req_data = json.dumps([dict(commit_hash='abc123', distro_hash='abc123',
                                    promote_name='foo'),
                               dict(commit_hash='abc456', distro_hash='abc456',
                                    promote_name='foo')])
        response = self.app.post('/api/promote-batch',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)

    @mock.patch('os.symlink')
    def test_promote_batch_successful_1(self, sl_mock, db2_mock, db_mock):
        req_data = json.dumps([dict(commit_hash='1c67b1ab8c6fe273d4e'
                                                '175a14f0df5d3cbbd0edc',
                                    distro_hash='8170b8686c38bafb6021'
                                                'd998e2fb268ab26ccf65',
                                    promote_name='foo-ci')])
        response = self.app.post('/api/promote-batch',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')

        expected = [mock.call('1c/67/1c67b1ab8c6fe273d4e175a'
                              '14f0df5d3cbbd0edc_8170b868', '/tmp/foo-ci')]

        self.assertEqual(response.status_code, 201)
        self.assertEqual(sl_mock.call_args_list, expected)

    @mock.patch('os.symlink')
    def test_promote_batch_successful_2(self, sl_mock, db2_mock, db_mock):
        req_data = json.dumps([dict(commit_hash='1c67b1ab8c6fe273d4e'
                                                '175a14f0df5d3cbbd0edc',
                                    distro_hash='8170b8686c38bafb6021'
                                                'd998e2fb268ab26ccf65',
                                    promote_name='foo-ci'),
                               dict(commit_hash='17234e9ab9dfab4cf560'
                                                '0f67f1d24db5064f1025',
                                    distro_hash='024e24f0cf4366c2290c'
                                                '22f24e42de714d1addd1',
                                    promote_name='foo-ci'),
                               ])
        response = self.app.post('/api/promote-batch',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')

        expected = [mock.call('1c/67/1c67b1ab8c6fe273d4e175a'
                              '14f0df5d3cbbd0edc_8170b868', '/tmp/foo-ci'),
                    mock.call('component/tripleo/17/23/17234e9ab9dfab4cf56'
                              '00f67f1d24db5064f1025_024e24f0', '/tmp/foo-ci')]
        self.assertEqual(response.status_code, 201)
        self.assertEqual(sl_mock.call_args_list, expected)

    @mock.patch('os.symlink')
    def test_promote_batch_successful_exthash(self, sl_mock, db2_mock,
                                              db_mock):
        req_data = json.dumps([dict(commit_hash='1c67b1ab8c6fe273d4e'
                                                '175a14f0df5d3cbbd0edc',
                                    distro_hash='8170b8686c38bafb6021'
                                                'd998e2fb268ab26ccf65',
                                    promote_name='test-ci'),
                               dict(commit_hash='93eee77657978547f5fad'
                                                '1cb8cd30b570da83e68',
                                    distro_hash='008678d7b0e20fbae185f'
                                                '2bb1bd0d9d167586211',
                                    extended_hash='1234567890_1234567890',
                                    promote_name='test-ci'),
                               ])
        response = self.app.post('/api/promote-batch',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')

        expected = [mock.call('1c/67/1c67b1ab8c6fe273d4e175a'
                              '14f0df5d3cbbd0edc_8170b868', '/tmp/test-ci'),
                    mock.call('component/tripleo/93/ee/93eee77657978547f5fad'
                              '1cb8cd30b570da83e68_008678d7_12345678',
                              '/tmp/test-ci')]
        self.assertEqual(response.status_code, 201)
        self.assertEqual(sl_mock.call_args_list, expected)

    @mock.patch('dlrn.api.dlrn_api.aggregate_repo_files', side_effect=mock_ag)
    @mock.patch('dlrn.api.dlrn_api._get_config_options', side_effect=mock_opt)
    @mock.patch('os.symlink')
    def test_promote_batch_successful_2_cmp(self, sl_mock, co_mock, ag_mock,
                                            db2_mock, db_mock):
        req_data = json.dumps([dict(commit_hash='1c67b1ab8c6fe273d4e'
                                                '175a14f0df5d3cbbd0edc',
                                    distro_hash='8170b8686c38bafb6021'
                                                'd998e2fb268ab26ccf65',
                                    promote_name='foo-ci'),
                               dict(commit_hash='17234e9ab9dfab4cf560'
                                                '0f67f1d24db5064f1025',
                                    distro_hash='024e24f0cf4366c2290c'
                                                '22f24e42de714d1addd1',
                                    promote_name='foo-ci')])
        response = self.app.post('/api/promote-batch',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')

        expected = [mock.call('1c/67/1c67b1ab8c6fe273d4e175a'
                              '14f0df5d3cbbd0edc_8170b868',
                              '/tmp/component/None/foo-ci'),
                    mock.call('17/23/17234e9ab9dfab4cf5600f67f1d24db5064'
                              'f1025_024e24f0',
                              '/tmp/component/tripleo/foo-ci')]

        data = json.loads(response.data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(data['commit_hash'], '17234e9ab9dfab4cf560'
                                              '0f67f1d24db5064f1025')
        self.assertEqual(data['distro_hash'], '024e24f0cf4366c2290c'
                                              '22f24e42de714d1addd1')
        self.assertEqual(data['promote_name'], 'foo-ci')
        self.assertEqual(data['component'], 'tripleo')
        self.assertEqual(data['aggregate_hash'], 'abc123')
        self.assertEqual(data['user'], 'foo')
        self.assertEqual(sl_mock.call_args_list, expected)
        self.assertEqual(ag_mock.call_count, 1)


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestRepoStatus(DLRNAPITestCase):
    def test_repo_status_missing_commit(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='abc123', distro_hash='abc123'))
        response = self.app.get('/api/repo_status',
                                data=req_data,
                                content_type='application/json')

        self.assertEqual(response.status_code, 400)

    def test_repo_status_missing_commit_url_param(self, db2_mock, db_mock):
        response = self.app.get('/api/repo_status?commit_hash=abc123'
                                '&distro_hash=abc123')
        self.assertEqual(response.status_code, 400)

    def test_repo_status_multiple_votes(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='17234e9ab9dfab4cf5600f'
                                               '67f1d24db5064f1025',
                                   distro_hash='024e24f0cf4366c2290c22'
                                               'f24e42de714d1addd1'))
        response = self.app.get('/api/repo_status',
                                data=req_data,
                                content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)

    def test_repo_status_multiple_votes_url_param(self, db2_mock, db_mock):
        response = self.app.get('/api/repo_status?commit_hash='
                                '17234e9ab9dfab4cf5600f67f1d24db5064f1025&'
                                'distro_hash=024e24f0cf4366c2290c22f24e42d'
                                'e714d1addd1')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)

    def test_repo_status_with_success(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='17234e9ab9dfab4cf5600f'
                                               '67f1d24db5064f1025',
                                   distro_hash='024e24f0cf4366c2290c22'
                                               'f24e42de714d1addd1',
                                   success='true'))
        response = self.app.get('/api/repo_status',
                                data=req_data,
                                content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)

    def test_repo_status_with_success_url_param(self, db2_mock, db_mock):
        response = self.app.get('/api/repo_status?commit_hash='
                                '17234e9ab9dfab4cf5600f67f1d24db5064f1025&'
                                'distro_hash=024e24f0cf4366c2290c22f24e42d'
                                'e714d1addd1&success=true')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)

    def test_repo_status_extended_hash(self, db2_mock, db_mock):
        response = self.app.get('/api/repo_status?commit_hash='
                                '93eee77657978547f5fad1cb8cd30b570da83e68&'
                                'distro_hash=008678d7b0e20fbae185f2bb1bd0d'
                                '9d167586211&extended_hash='
                                '1234567890_1234567890')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['extended_hash'], '1234567890_1234567890')


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestAggStatus(DLRNAPITestCase):
    def test_agg_status_missing_hash(self, db2_mock, db_mock):
        response = self.app.get('/api/agg_status?success=true')
        self.assertEqual(response.status_code, 400)

    def test_agg_status_multiple_votes(self, db2_mock, db_mock):
        response = self.app.get('/api/agg_status?aggregate_hash=12345678')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)

    def test_agg_status_with_success(self, db2_mock, db_mock):
        response = self.app.get('/api/agg_status?aggregate_hash=12345678&'
                                'success=true')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)

    def test_agg_status_hash_not_found(self, db2_mock, db_mock):
        response = self.app.get('/api/agg_status?aggregate_hash=000000000')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 0)


@mock.patch('dlrn.remote.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestRemoteImport(DLRNAPITestCase):
    def test_post_remote_import_needs_auth(self, db2_mock, db_mock):
        response = self.app.post('/api/remote/import')
        self.assertEqual(response.status_code, 401)

    @mock.patch('os.rename')
    @mock.patch('os.symlink')
    @mock.patch('dlrn.drivers.rdoinfo.RdoInfoDriver.getpackages')
    @mock.patch.object(sh.Command, '__call__', autospec=True)
    @mock.patch('dlrn.remote.post_build')
    @mock.patch('dlrn.remote.urlopen', side_effect=mocked_urlopen)
    def test_post_remote_import_success(self, url_mock, build_mock, sh_mock,
                                        db2_mock, db_mock, gp_mock, sl_mock,
                                        rn_mock):

        req_data = json.dumps(dict(repo_url='http://example.com/1/'))

        header = {'Authorization': 'Basic %s' % (
                  base64.b64encode(b'foo:bar').decode('ascii'))}

        response = self.app.post('/api/remote/import',
                                 data=req_data,
                                 headers=header,
                                 content_type='application/json')

        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['repo_url'], 'http://example.com/1/')


@mock.patch('dlrn.api.dlrn_api.render_template', side_effect=' ')
@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestGetCIVotes(DLRNAPITestCase):
    def test_get_civotes(self, db2_mock, db_mock, rt_mock):
        response = self.app.get('/api/civotes.html')
        self.assertEqual(rt_mock.call_count, 1)
        self.assertEqual(response.status_code, 200)

    def test_get_civotes_detail_fail(self, db2_mock, db_mock, rt_mock):
        response = self.app.get('/api/civotes_detail.html')
        self.assertEqual(response.status_code, 400)

    def test_get_civotes_detail_ok(self, db2_mock, db_mock, rt_mock):
        response = self.app.get('/api/civotes_detail.html?'
                                'commit_hash=17234e9ab9dfab4cf5600f67f1d24db5'
                                '064f1025&distro_hash=024e24f0cf4366c2290c22f'
                                '24e42de714d1addd1')
        self.assertEqual(rt_mock.call_count, 1)
        self.assertEqual(response.status_code, 200)

    def test_get_civotes_detail_with_ci(self, db2_mock, db_mock, rt_mock):
        response = self.app.get('/api/civotes_detail.html?'
                                'ci_name=another-ci')
        self.assertEqual(rt_mock.call_count, 1)
        self.assertEqual(response.status_code, 200)


@mock.patch('dlrn.api.dlrn_api.render_template', side_effect=' ')
@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestGetCIAggVotes(DLRNAPITestCase):
    def test_get_ciaggvotes(self, db2_mock, db_mock, rt_mock):
        response = self.app.get('/api/civotes_agg.html')
        self.assertEqual(rt_mock.call_count, 1)
        self.assertEqual(response.status_code, 200)

    def test_get_ciaggvotes_detail_fail(self, db2_mock, db_mock, rt_mock):
        response = self.app.get('/api/civotes_agg_detail.html')
        self.assertEqual(response.status_code, 400)

    def test_get_ciaggvotes_detail_ok(self, db2_mock, db_mock, rt_mock):
        response = self.app.get('/api/civotes_agg_detail.html?'
                                'ref_hash=12345678')
        self.assertEqual(rt_mock.call_count, 1)
        self.assertEqual(response.status_code, 200)

    def test_get_ciaggvotes_detail_with_ci(self, db2_mock, db_mock, rt_mock):
        response = self.app.get('/api/civotes_agg_detail.html?'
                                'ci_name=phase2-ci')
        self.assertEqual(rt_mock.call_count, 1)
        self.assertEqual(response.status_code, 200)


@mock.patch('dlrn.api.dlrn_api.render_template', side_effect=' ')
@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestGetReport(DLRNAPITestCase):
    def test_get_report(self, commit_mock, db2_mock, db_mock):
        response = self.app.get('/api/report.html')
        self.assertEqual(response.status_code, 200)


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestGetPromotions(DLRNAPITestCase):
    def test_get_promotions_missing_commit(self, db2_mock, db_mock):
        req_data = json.dumps(dict(distro_hash='abc123'))
        response = self.app.get('/api/promotions',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_get_promotions_no_such_commit(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='abc123',
                              distro_hash='abc123'))
        response = self.app.get('/api/promotions',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_get_promotions_no_such_commit_url_params(self, db2_mock,
                                                      db_mock):
        response = self.app.get('/api/promotions?commit_hash=abc123&'
                                'distro_hash=abc123')
        self.assertEqual(response.status_code, 400)

    def test_get_promotions_multiple_votes(self, db2_mock, db_mock):
        req_data = '{}'
        response = self.app.get('/api/promotions',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 4)

    def test_get_promotions_multiple_votes_url_params(self, db2_mock, db_mock):
        response = self.app.get('/api/promotions')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 4)

    def test_get_promotions_with_promote_name(self, db2_mock, db_mock):
        req_data = json.dumps(dict(promote_name='another-ci'))
        response = self.app.get('/api/promotions',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)

    def test_get_promotions_with_promote_name_url_params(self, db2_mock,
                                                         db_mock):
        response = self.app.get('/api/promotions?promote_name=another-ci')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)

    def test_get_promotions_with_commit(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='17234e9ab9dfab4cf5600f67f1'
                                               'd24db5064f1025',
                                   distro_hash='024e24f0cf4366c2290c22f24e'
                                               '42de714d1addd1'))
        response = self.app.get('/api/promotions',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)

    def test_get_promotions_with_ext_hash(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='93eee77657978547f5fad1cb8c'
                                               'd30b570da83e68',
                                   distro_hash='008678d7b0e20fbae185f2bb1b'
                                               'd0d9d167586211',
                                   extended_hash='1234567890_1234567890'))
        response = self.app.get('/api/promotions',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['extended_hash'], '1234567890_1234567890')

    def test_get_promotions_with_offset(self, db2_mock, db_mock):
        req_data = json.dumps(dict(offset=1))
        response = self.app.get('/api/promotions',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 3)

    def test_get_promotions_with_offset_url_params(self, db2_mock, db_mock):
        response = self.app.get('/api/promotions?offset=1')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 3)

    def test_get_promotions_with_limit(self, db2_mock, db_mock):
        req_data = json.dumps(dict(limit=1))
        response = self.app.get('/api/promotions',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)

    def test_get_promotions_with_limit_url_param(self, db2_mock, db_mock):
        response = self.app.get('/api/promotions?limit=1')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)

    def test_get_promotions_same_timestamp(self, db2_mock, db_mock):
        response = self.app.get('/api/promotions?promote_name=foo-ci&limit=2')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['aggregate_hash'], 'abcd1234')
        # This proves that the second commit, with the same timestamp, is the
        # one with a lower id
        self.assertEqual(data[1]['aggregate_hash'], None)


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestMetrics(DLRNAPITestCase):
    def test_metrics_missing_start_date(self, db2_mock, db_mock):
        req_data = json.dumps(dict(end_date='0'))
        response = self.app.get('/api/metrics/builds',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_metrics_missing_start_date_url_param(self, db2_mock, db_mock):
        response = self.app.get('/api/metrics/builds?end_date=0')
        self.assertEqual(response.status_code, 400)

    def test_metrics_wrong_date_format(self, db2_mock, db_mock):
        req_data = json.dumps(dict(start_date='0', end_date='0'))
        response = self.app.get('/api/metrics/builds',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_metrics_wrong_date_format_url_param(self, db2_mock, db_mock):
        response = self.app.get('/api/metrics/builds?start_date=0&end_date=0')
        self.assertEqual(response.status_code, 400)

    def test_metrics_notindate(self, db2_mock, db_mock):
        req_data = json.dumps(dict(start_date='2011-09-07',
                                   end_date='2011-09-09'))
        response = self.app.get('/api/metrics/builds',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['total'], 0)
        self.assertEqual(data['succeeded'], 0)
        self.assertEqual(data['failed'], 0)

    def test_metrics_success(self, db2_mock, db_mock):
        req_data = json.dumps(dict(start_date='2015-09-07',
                                   end_date='2015-09-09'))
        response = self.app.get('/api/metrics/builds',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['total'], 5)
        self.assertEqual(data['succeeded'], 5)
        self.assertEqual(data['failed'], 0)

    def test_metrics_success_url_param(self, db2_mock, db_mock):
        response = self.app.get('/api/metrics/builds?start_date=2015-09-07'
                                '&end_date=2015-09-09')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['total'], 5)
        self.assertEqual(data['succeeded'], 5)
        self.assertEqual(data['failed'], 0)

    def test_metrics_filtered(self, db2_mock, db_mock):
        req_data = json.dumps(dict(start_date='2015-09-07',
                                   end_date='2015-09-09',
                                   package_name='python-pysaml2'))
        response = self.app.get('/api/metrics/builds',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['succeeded'], 1)
        self.assertEqual(data['failed'], 0)

    def test_metrics_filtered_url_param(self, db2_mock, db_mock):
        response = self.app.get('/api/metrics/builds?start_date=2015-09-07'
                                '&end_date=2015-09-09&'
                                'package_name=python-pysaml2')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['succeeded'], 1)
        self.assertEqual(data['failed'], 0)

    def test_metrics_filtered_nopackage(self, db2_mock, db_mock):
        req_data = json.dumps(dict(start_date='2015-09-07',
                                   end_date='2015-09-09',
                                   package_name='python-pysaml'))
        response = self.app.get('/api/metrics/builds',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['total'], 0)

    def test_metrics_filtered_nopackage_url_param(self, db2_mock, db_mock):
        response = self.app.get('/api/metrics/builds?start_date=2015-09-07'
                                '&end_date=2015-09-09&'
                                'package_name=python-pysaml')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['total'], 0)


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestHealth(DLRNAPITestCase):
    def test_health_get(self, db2_mock, db_mock):
        response = self.app.get('/api/health')
        self.assertEqual(response.status_code, 200)

    def test_health_post_ok(self, db2_mock, db_mock):
        req_data = json.dumps(dict(test='test'))
        response = self.app.post('/api/health',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def test_health_post_nouser(self, db2_mock, db_mock):
        response = self.app.post('/api/health')
        self.assertEqual(response.status_code, 401)

    def test_health_post_wrong_user(self, db2_mock, db_mock):
        headers = {'Authorization': 'Basic %s' % (
            base64.b64encode(b'blabla:blabla').decode('ascii'))}
        response = self.app.post('/api/health',
                                 headers=headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_health_put_wrong_method(self, db2_mock, db_mock):
        response = self.app.put('/api/health',
                                headers=self.headers,
                                content_type='application/json')
        # Error 405 is "method not allowed"
        self.assertEqual(response.status_code, 405)
