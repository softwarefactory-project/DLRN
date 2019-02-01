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
import tempfile

from datetime import datetime
from dlrn.api import app
from dlrn import db
from dlrn.tests import base
from dlrn import utils
from flask import json
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
    def test_get_last_tested_repo_needs_json(self, db_mock, dt_mock):
        response = self.app.get('/api/last_tested_repo')
        self.assertEqual(response.status_code, 415)

    def test_get_last_tested_repo_no_results(self, db_mock, dt_mock):
        req_data = json.dumps(dict(max_age='48'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.get('/api/last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 404)

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
        self.assertEqual(response.status_code, 200)

    def test_get_last_tested_repo_noconstraints(self, db_mock, dt_mock):
        req_data = json.dumps(dict(max_age='0'))
        dt_mock.now.return_value = datetime.fromtimestamp(1441901490)
        response = self.app.get('/api/last_tested_repo',
                                data=req_data,
                                content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(data['commit_hash'],
                         '1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edc')
        self.assertEqual(data['distro_hash'],
                         '8170b8686c38bafb6021d998e2fb268ab26ccf65')
        self.assertEqual(data['job_id'], 'another-ci')
        self.assertEqual(response.status_code, 200)

    def test_get_last_tested_repo_non_existing_ci(self, db_mock, dt_mock):
        req_data = json.dumps(dict(max_age='0', job_id='foo'))
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
        self.assertEqual(response.status_code, 200)

    def test_get_last_tested_repo_existing_ci(self, db_mock, dt_mock):
        req_data = json.dumps(dict(max_age='0',
                                   job_id='current-passed-ci'))
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

    def test_get_last_tested_repo_failed(self, db_mock, dt_mock):
        req_data = json.dumps(dict(max_age='0', success='0'))
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
        self.assertEqual(response.status_code, 404)


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
                         '1c67b1ab8c6fe273d4e175a14f0df5d3cbbd0edc')
        self.assertEqual(data['distro_hash'],
                         '8170b8686c38bafb6021d998e2fb268ab26ccf65')
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
        self.assertEqual(response.status_code, 404)


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
        self.assertEqual(response.status_code, 404)

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

        self.assertEqual(response.status_code, 404)

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
        self.assertEqual(data['message'], 'commit_hash+distro_hash has been'
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
class TestRepoStatus(DLRNAPITestCase):
    def test_get_last_tested_repo_needs_json(self, db2_mock, db_mock):
        response = self.app.get('/api/repo_status')
        self.assertEqual(response.status_code, 415)

    def test_repo_status_missing_commit(self, db2_mock, db_mock):
        req_data = json.dumps(dict(commit_hash='abc123', distro_hash='abc123'))
        response = self.app.get('/api/repo_status',
                                data=req_data,
                                content_type='application/json')

        self.assertEqual(response.status_code, 404)

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


@mock.patch('dlrn.remote.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestRemoteImport(DLRNAPITestCase):
    def test_post_remote_import_needs_auth(self, db2_mock, db_mock):
        response = self.app.post('/api/remote/import')
        self.assertEqual(response.status_code, 401)

    @mock.patch('dlrn.drivers.rdoinfo.RdoInfoDriver.getpackages')
    @mock.patch.object(sh.Command, '__call__', autospec=True)
    @mock.patch('dlrn.remote.post_build')
    @mock.patch('dlrn.remote.urlopen', side_effect=mocked_urlopen)
    def test_post_remote_import_success(self, url_mock, build_mock, sh_mock,
                                        db2_mock, db_mock, gp_mock):

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
class TestGetReport(DLRNAPITestCase):
    def test_get_report(self, db2_mock, db_mock, rt_mock):
        response = self.app.get('/api/report.html')
        self.assertEqual(rt_mock.call_count, 1)
        self.assertEqual(response.status_code, 200)

    def test_get_report_detail(self, db2_mock, db_mock, rt_mock):
        response = self.app.get('/api/report.html?project=python-pysaml2'
                                '&success=1')
        self.assertEqual(rt_mock.call_count, 1)
        self.assertEqual(response.status_code, 200)


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestGetPromotions(DLRNAPITestCase):
    def test_get_promotions_needs_json(self, db2_mock, db_mock):
        response = self.app.get('/api/promotions')
        self.assertEqual(response.status_code, 415)

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
        self.assertEqual(response.status_code, 404)

    def test_get_promotions_multiple_votes(self, db2_mock, db_mock):
        req_data = '{}'
        response = self.app.get('/api/promotions',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)

    def test_get_promotions_with_promote_name(self, db2_mock, db_mock):
        req_data = json.dumps(dict(promote_name='another-ci'))
        response = self.app.get('/api/promotions',
                                data=req_data,
                                content_type='application/json')
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

    def test_get_promotions_with_offset(self, db2_mock, db_mock):
        req_data = json.dumps(dict(offset=1))
        response = self.app.get('/api/promotions',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)

    def test_get_promotions_with_limit(self, db2_mock, db_mock):
        req_data = json.dumps(dict(limit=1))
        response = self.app.get('/api/promotions',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session)
@mock.patch('dlrn.api.utils.getSession', side_effect=mocked_session)
class TestMetrics(DLRNAPITestCase):
    def test_metrics_json(self, db2_mock, db_mock):
        response = self.app.get('/api/metrics/builds')
        self.assertEqual(response.status_code, 415)

    def test_metrics_missing_start_date(self, db2_mock, db_mock):
        req_data = json.dumps(dict(end_date='0'))
        response = self.app.get('/api/metrics/builds',
                                data=req_data,
                                content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_metrics_wrong_date_format(self, db2_mock, db_mock):
        req_data = json.dumps(dict(start_date='0', end_date='0'))
        response = self.app.get('/api/metrics/builds',
                                data=req_data,
                                content_type='application/json')
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
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['succeeded'], 3)
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
