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
import unittest
from unittest.mock import patch

from datetime import datetime
from dlrn.api.api_logging import create_logger_dict
from dlrn.api.api_logging import create_rotating_file_handler_dict
from dlrn.api.api_logging import get_config
from dlrn.api.api_logging import setup_dict_config
from dlrn.api import app
from dlrn.api import dlrn_api
from dlrn.api.drivers.auth import Auth
from dlrn.api.utils import ConfigurationValidator
from dlrn.config import ConfigOptions
from dlrn import db
from dlrn.tests import base
from dlrn import utils
from flask import json
# Skipping Kerberos tests if DLRN was installed without Kerberos option.
try:
    import ipalib
    from ipalib.errors import PublicError
except ModuleNotFoundError:
    ipalib = None
    PublicError = Exception

try:
    import gssapi
except ModuleNotFoundError:
    gssapi = None
from six.moves import configparser

TEST_SUCCESS_ROLE = "test_success_role"
TEST_WRONG_ROLE = "test_wrong_role"


def mocked_session(*args, **kwargs):
    def wrapper(url=None, commit_file=None, raise_exception=None):
        # Specifies the file to populate to the DB session
        commit_file = kwargs["commit_file"] if "commit_file" in kwargs.keys() \
            else None
        # Specifies if an Exception should be raised when commiting
        raise_exception = kwargs["raise_exception"] if "raise_exception" \
            in kwargs.keys() else None
        db_fd, filepath = tempfile.mkstemp()
        session = db.getSession("sqlite:///%s" % filepath)
        if not commit_file:
            utils.loadYAML(session, "./dlrn/tests/samples/commits_2.yaml")
        else:
            utils.loadYAML(session, commit_file)
        if raise_exception:
            session.commit = mock.Mock()
            session.commit.side_effect = Exception("Test Exception")
        return session
    return wrapper


def mocked_get(url, timeout=None):
    mock_resp = mock.Mock()
    with open('./dlrn/tests/samples/commits_remote.yaml', 'rb') as fp:
        mock_resp.status_code = 200
        mock_resp.content = fp.read()
        mock_resp.text = mock_resp.content.decode('utf-8')
    return mock_resp


def mock_opt(config_file):
    cp = configparser.RawConfigParser()
    cp.read(config_file)
    co = ConfigOptions(cp)
    co.use_components = True
    return co


def mock_ag(dirname, datadir, session, reponame, packages, hashed_dir=False):
    return 'abc123'


def mock_logger_dict(logger_name, handler_name, log_level):
    return {logger_name: {'level': log_level,
                          'handlers': [handler_name],
                          'propagate': False}}


def mock_handler_dict(handler_name, file_path):
    return {handler_name: {'class': 'logging.handlers.RotatingFileHandler',
                           'filename': file_path,
                           'backupCount': 3,
                           'maxBytes': 15728640,
                           'formatter': 'default'}}


@dlrn_api.app.route('/api/test_auth', methods=['POST'])
@dlrn_api.auth_multi.login_required(optional=False, role=TEST_SUCCESS_ROLE)
def test_health():
    from flask import jsonify
    return jsonify({'result': 'ok'}), 200


class DLRNAPITestCase(base.TestCase):
    def setUp(self):
        super(DLRNAPITestCase, self).setUp()
        self.db_fd, self.filepath = tempfile.mkstemp()
        app.config['DB_PATH'] = "sqlite:///%s" % self.filepath
        app.config['REPO_PATH'] = '/tmp'
        self.setup_default_auth()
        self.app = app.test_client()
        self.app.testing = True
        self.headers = {'Authorization': 'Basic %s' % (
            base64.b64encode(b'foo:bar').decode('ascii'))}

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.filepath)
        super(DLRNAPITestCase, self).tearDown()

    def setup_default_auth(self):
        default_driver = "dlrn.api.drivers.dbauthentication.DBAuthentication"
        db_auth = utils.import_class(default_driver)()
        dlrn_api.auth_multi.main_auth = db_auth
        dlrn_api.auth_multi.additional_auth = []


class DLRNAPITestCaseKrb(DLRNAPITestCase):
    from dlrn.api.drivers.krbauthentication import IPAAuthorization
    from dlrn.api.drivers.krbauthentication import KrbAuthentication

    def setUp(self):
        super(DLRNAPITestCaseKrb, self).setUp()
        self.KrbAuthentication.gssapi = gssapi
        self.IPAAuthorization.api = ipalib.api
        self.headers = {'Authorization': 'Negotiate VE9LRU4='}
        app.config['KEYTAB_PATH'] = ".keytab"
        app.config['KEYTAB_PRINC'] = "keytab_principal"
        app.config['HTTP_KEYTAB_PATH'] = "http_keytab_principal"
        self.setup_kerberos_auth()

    def tearDown(self):
        super(DLRNAPITestCaseKrb, self).tearDown()
        # Returning to the default global state.
        self.setup_default_auth()

    def setup_kerberos_auth(self):
        krb_driver = "dlrn.api.drivers.krbauthentication.KrbAuthentication"
        krb_auth = utils.import_class(krb_driver)()
        dlrn_api.auth_multi.main_auth = krb_auth
        dlrn_api.auth_multi.additional_auth = []


@mock.patch('dlrn.api.dlrn_api.datetime')
@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
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
@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
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


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
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


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
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


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
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


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
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


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
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


@mock.patch('dlrn.remote.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
class TestRemoteImport(DLRNAPITestCase):
    def test_post_remote_import_needs_auth(self, db2_mock, db_mock):
        response = self.app.post('/api/remote/import')
        self.assertEqual(response.status_code, 401)

    @mock.patch('os.rename')
    @mock.patch('os.symlink')
    @mock.patch('dlrn.drivers.rdoinfo.RdoInfoDriver.getpackages')
    @mock.patch.object(sh.Command, '__call__', autospec=True)
    @mock.patch('dlrn.remote.post_build')
    @mock.patch('dlrn.remote.requests.get', side_effect=mocked_get)
    def test_post_remote_import_success(self, get_mock, build_mock, sh_mock,
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
@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
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
@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
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
@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
class TestGetReport(DLRNAPITestCase):
    def test_get_report(self, commit_mock, db2_mock, db_mock):
        response = self.app.get('/api/report.html')
        self.assertEqual(response.status_code, 200)


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
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


@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session(
                commit_file='./dlrn/tests/samples/commits_3.yaml'))
class TestRecheckPackage(DLRNAPITestCase):
    def test_recheck_package_no_package_name(self, db_mock):
        self.headers = {'Authorization': 'Basic %s' % (
            base64.b64encode(b'foo:bar').decode('ascii'))}
        response = self.app.post('/api/recheck_package',
                                 data="",
                                 headers=self.headers,
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 400)
        self.assertRegex(data["message"], "Missing parameters:")

    @mock.patch('dlrn.api.dlrn_api.getSession',
                side_effect=mocked_session(
                    commit_file='./dlrn/tests/samples/commits_3.yaml'))
    def test_recheck_package_no_commit(self, db_mock, db2_mock):
        self.headers = {'Authorization': 'Basic %s' % (
            base64.b64encode(b'foo:bar').decode('ascii'))}
        response = self.app.post('/api/recheck_package?package_name=foo-ci',
                                 data="",
                                 headers=self.headers,
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 400)
        self.assertRegex(data["message"], "There are no existing commits")

    @mock.patch('dlrn.api.dlrn_api.getSession',
                side_effect=mocked_session(
                    commit_file='./dlrn/tests/samples/commits_3.yaml'))
    def test_recheck_package_commit_success(self, db_mock, db2_mock):
        self.headers = {'Authorization': 'Basic %s' % (
            base64.b64encode(b'foo:bar').decode('ascii'))}
        endpoint = '/api/recheck_package?package_name=python-pysaml2'
        response = self.app.post(endpoint,
                                 data="",
                                 headers=self.headers,
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 409)
        self.assertRegex(data["message"], "It's not possible to recheck a "
                         "successful commit")

    @mock.patch('dlrn.api.dlrn_api.getSession',
                side_effect=mocked_session(
                    commit_file='./dlrn/tests/samples/commits_3.yaml'))
    def test_recheck_package_commit_failed(self, db_mock, db2_mock):
        self.headers = {'Authorization': 'Basic %s' % (
            base64.b64encode(b'foo:bar').decode('ascii'))}
        endpoint = '/api/recheck_package?package_name=python-stevedore'
        response = self.app.post(endpoint,
                                 data="",
                                 headers=self.headers,
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 201)
        self.assertRegex(data['result'], "ok")

    @mock.patch('dlrn.api.dlrn_api.getSession',
                side_effect=mocked_session(
                    commit_file='./dlrn/tests/samples/commits_3.yaml',
                    raise_exception=True))
    def test_recheck_package_commit_failed_exception(self, db_mock, db2_mock):
        self.headers = {'Authorization': 'Basic %s' % (
            base64.b64encode(b'foo:bar').decode('ascii'))}
        endpoint = '/api/recheck_package?package_name=python-stevedore'
        response = self.app.post(endpoint,
                                 data="",
                                 headers=self.headers,
                                 content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 500)
        self.assertRegex(data['message'], "Error occurred while committing "
                         "changes to database")


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
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


@mock.patch('dlrn.api.dlrn_api.getSession',
            side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
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


class TestAuthConfiguration(base.TestCase):
    from dlrn.api.drivers.dbauthentication import DBAuthentication
    from dlrn.api.drivers.krbauthentication import KrbAuthentication

    def test_default_auth_conf(self):
        config = {'AUTHENTICATION_DRIVERS': []}
        with self.assertLogs("logger_dlrn", level="INFO") as cm:
            auth = Auth(config).auth_multi
            self.assertRegex(''.join(cm.output), 'Default auth driver loaded.')

        self.assertIsInstance(auth.main_auth, self.DBAuthentication)

    def test_non_existing_driver_conf(self):
        config = {'AUTHENTICATION_DRIVERS': ["non_existing_driver"]}
        with self.assertLogs("logger_dlrn", level="ERROR") as cm:
            auth = Auth(config).auth_multi
            self.assertEqual(cm.output, ["ERROR:logger_dlrn:Driver not found:"
                                         " 'non_existing_driver'"])
        self.assertIsInstance(auth.main_auth, self.DBAuthentication)

    def test_db_driver_conf(self):
        config = {'AUTHENTICATION_DRIVERS': ["DBAuthentication"]}
        with self.assertLogs("logger_dlrn", level="INFO") as cm:
            auth = Auth(config).auth_multi
            self.assertRegex(''.join(cm.output), 'Added auth driver: '
                             'DBAuthentication')
        self.assertIsInstance(auth.main_auth, self.DBAuthentication)

    def test_krb_driver_conf(self):
        config = {'AUTHENTICATION_DRIVERS': ["KrbAuthentication"]}
        app.config['KEYTAB_PATH'] = ".keytab"
        app.config['KEYTAB_PRINC'] = "keytab_principal"
        app.config['HTTP_KEYTAB_PATH'] = "http_keytab_principal"

        with self.assertLogs("logger_dlrn", level="INFO") as cm:
            auth = Auth(config).auth_multi
            self.assertEqual(cm.output, ['INFO:logger_dlrn:Added auth driver:'
                                         ' KrbAuthentication'])
        self.assertIsInstance(auth.main_auth, self.KrbAuthentication)

    def test_multiple_driver_conf(self):
        config = {'AUTHENTICATION_DRIVERS': ["KrbAuthentication",
                                             "DBAuthentication"]}
        app.config['KEYTAB_PATH'] = ".keytab"
        app.config['KEYTAB_PRINC'] = "keytab_principal"
        app.config['HTTP_KEYTAB_PATH'] = "http_keytab_principal"

        auth = Auth(config).auth_multi
        self.assertIsInstance(auth.main_auth, self.KrbAuthentication)
        self.assertIsInstance(auth.additional_auth[0], self.DBAuthentication)


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
@mock.patch('dlrn.api.drivers.dbauthentication.getSession',
            side_effect=mocked_session())
class TestDBAuthDriver(DLRNAPITestCase):

    def test_basic_auth_no_headers(self, db2_mock, db_mock):
        self.headers = {}
        req_data = json.dumps(dict(test='test'))
        with self.assertLogs("logger_dlrn", level="ERROR") as cm:
            response = self.app.post('/api/health',
                                     data=req_data,
                                     headers=self.headers,
                                     content_type='application/json')
            self.assertEqual(cm.output, ['ERROR:logger_dlrn:No user or'
                                         ' password in the request headers.'])

        self.assertEqual(response.status_code, 401)

    def test_basic_auth_success(self, db2_mock, db_mock):
        req_data = json.dumps(dict(test='test'))
        self.headers = {'Authorization': 'Basic %s' % (
            base64.b64encode(b'foo:bar').decode('ascii'))}
        response = self.app.post('/api/health',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(db2_mock.call_count, 1)

    def test_basic_auth_wrong_credentials(self, db2_mock, db_mock):
        req_data = json.dumps(dict(test='test'))
        self.headers = {'Authorization': 'Basic %s' % (
            base64.b64encode(b'foo:wrong_password').decode('ascii'))}
        response = self.app.post('/api/health',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(db2_mock.call_count, 1)


@mock.patch('dlrn.api.dlrn_api.getSession', side_effect=mocked_session())
class TestKrbAuthDriver(DLRNAPITestCaseKrb):
    class CustomError(Exception):
        pass

    class CustomError2(Exception):
        pass

    @unittest.skipIf(gssapi is None or ipalib is None,
                     "gssapi or ipalib modules not installed")
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".__init__", return_value=None)
    @mock.patch('dlrn.api.drivers.krbauthentication.KrbAuthentication'
                '.get_user')
    def test_kerberos_auth_success(self, gtuser_mock,
                                   ipaauth_mock, db_mock):
        req_data = json.dumps(dict(test='test'))
        response = self.app.post('/api/health',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(gtuser_mock.call_count, 1)

    @unittest.skipIf(gssapi is None or ipalib is None,
                     "gssapi or ipalib modules not installed")
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".__init__", return_value=None)
    @mock.patch('dlrn.api.drivers.krbauthentication.KrbAuthentication.'
                'authorize', return_value=False)
    @mock.patch('dlrn.api.drivers.krbauthentication.KrbAuthentication.'
                'get_user')
    def test_kerberos_auth_not_allowed(self, gtuser_mock,
                                       krbauth_authorize, ipaauth_mock,
                                       db_mock):
        req_data = json.dumps(dict(test='test'))
        response = self.app.post('/api/health',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(krbauth_authorize.call_count, 1)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(gtuser_mock.call_count, 1)

    @unittest.skipIf(gssapi is None or ipalib is None,
                     "gssapi or ipalib modules not installed")
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".__init__", return_value=None)
    def test_kerberos_auth_wrong_token(self, ipaauth_mock, db_mock):
        req_data = json.dumps(dict(test='test'))
        with self.assertLogs("logger_dlrn", level="ERROR") as cm:
            response = self.app.post('/api/health',
                                     data=req_data,
                                     headers=self.headers,
                                     content_type='application/json')
            self.assertEqual(cm.output, ['ERROR:logger_dlrn:Invalid token'
                                         ' while accessing "path": /api/health'
                                         ', "method": POST'])
        self.assertEqual(response.status_code, 401)

    @unittest.skipIf(gssapi is None or ipalib is None,
                     "gssapi or ipalib modules not installed")
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".__init__", return_value=None)
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".return_user_roles", return_value=[TEST_SUCCESS_ROLE])
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".disconnect_from_ipa")
    @mock.patch('dlrn.api.drivers.krbauthentication.KrbAuthentication'
                '.get_user', return_value="foo")
    def test_ipa_authorization_success(self, gtuser_mock, closeipa_mock,
                                       ipa_retr_roles, ipaauth_mock,
                                       db_mock):
        req_data = json.dumps(dict(test='test'))
        self.headers = {'Authorization': 'Negotiate VE9LRU4='}
        response = self.app.post('/api/test_auth',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(gtuser_mock.call_count, 1)
        self.assertEqual(ipa_retr_roles.call_count, 1)

    @unittest.skipIf(gssapi is None or ipalib is None,
                     "gssapi or ipalib modules not installed")
    @mock.patch('dlrn.api.drivers.krbauthentication.IPAAuthorization'
                '.return_user_roles', return_value=[TEST_WRONG_ROLE])
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".__init__", return_value=None)
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".disconnect_from_ipa")
    @mock.patch('dlrn.api.drivers.krbauthentication.KrbAuthentication'
                '.get_user', return_value="foo")
    def test_ipa_authorization_failure(self, gtuser_mock, closeipa_mock,
                                       ipa_retr_roles, get_roles, db_mock):
        req_data = json.dumps(dict(test='test'))
        response = self.app.post('/api/test_auth',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(gtuser_mock.call_count, 1)
        self.assertEqual(ipa_retr_roles.call_count, 1)

    @unittest.skipIf(gssapi is None or ipalib is None,
                     "gssapi or ipalib modules not installed")
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".__init__", return_value=None)
    # Mock an error while getting the roles of the given user.
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".execute_user_show", side_effect=KeyError)
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".disconnect_from_ipa")
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".connect_to_ipa_server")
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".retrieve_kerb_ticket")
    @mock.patch('dlrn.api.drivers.krbauthentication.KrbAuthentication'
                '.get_user', return_value="foo")
    def test_ipa_authorization_user_show_key_error(self, gtuser_mock,
                                                   retr_kerb, connect_ipa,
                                                   disconnect_ipa,
                                                   ipaallowed_mock,
                                                   ipaauth_mock, db_mock):
        req_data = json.dumps(dict(test='test'))
        response = self.app.post('/api/test_auth',
                                 data=req_data,
                                 headers=self.headers,
                                 content_type='application/json')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(gtuser_mock.call_count, 1)

    @unittest.skipIf(gssapi is None or ipalib is None,
                     "gssapi or ipalib modules not installed")
    @mock.patch("dlrn.api.drivers.krbauthentication.IPAAuthorization"
                ".return_user_roles", return_value=True)
    @mock.patch('dlrn.api.drivers.krbauthentication.KrbAuthentication'
                '.get_user')
    def test_kerb_auth_no_ipalib_module(self, gtuser_mock,
                                        ipaallowed_mock, db_mock):
        self.IPAAuthorization.api = None
        req_data = json.dumps(dict(test='test'))
        self.headers = {'Authorization': 'Negotiate VE9LRU4='}
        with self.assertLogs("logger_dlrn", level="ERROR") as cm:
            response = self.app.post('/api/test_auth',
                                     data=req_data,
                                     headers=self.headers,
                                     content_type='application/json')
            self.assertRegex(cm.output[0],
                             'Kerberos auth not enabled due to missing ipalib'
                             ' dependency')
        self.assertEqual(response.status_code, 500)

    @unittest.skipIf(gssapi is None or ipalib is None,
                     "gssapi or ipalib modules not installed")
    def test_kerb_auth_no_gssapi_module(self, db_mock):
        self.KrbAuthentication.gssapi = None
        req_data = json.dumps(dict(test='test'))
        self.headers = {'Authorization': 'Negotiate VE9LRU4='}
        with self.assertLogs("logger_dlrn", level="ERROR") as cm:
            response = self.app.post('/api/health',
                                     data=req_data,
                                     headers=self.headers,
                                     content_type='application/json')
            self.assertRegex(cm.output[0],
                             'Kerberos auth not enabled due to missing gssapi'
                             ' dependency')
        self.assertEqual(response.status_code, 500)

    @unittest.skipIf(gssapi is None or ipalib is None,
                     "gssapi or ipalib modules not installed")
    def test_ipa_authorization_retrieve_kerberos_kinit_Error(self, db_mock):
        from dlrn.api.drivers.krbauthentication import IPAAuthorization
        with self.assertLogs("logger_dlrn", level="ERROR") as cm:
            try:
                IPAAuthorization().return_user_roles()
            except Exception as e:
                self.assertRegex(cm.output[-1], 'ERROR:logger_dlrn:Maximum '
                                 'retries executed')
                self.assertIsInstance(e, Exception)

    @unittest.skipIf(gssapi is None or ipalib is None,
                     "gssapi or ipalib modules not installed")
    def test_ipa_authorization_decorator_success(self, db_mock):
        from dlrn.api.drivers.krbauthentication import retry_on_error
        action_msg = "Starting test message"
        success_msg = "Success test message"

        @retry_on_error(custom_error=self.CustomError,
                        action_msg=action_msg,
                        success_msg=success_msg)
        def to_be_decorated(self):
            return True
        with self.assertLogs("logger_dlrn", level="INFO") as cm:
            to_be_decorated(self)
            self.assertRegex(cm.output[0], action_msg)
            self.assertRegex(cm.output[1], success_msg)

    @unittest.skipIf(gssapi is None or ipalib is None,
                     "gssapi or ipalib modules not installed")
    def test_ipa_authorization_decorator_general_error(self, db_mock):
        from dlrn.api.drivers.krbauthentication import retry_on_error
        action_msg = "Starting test message"
        success_msg = "Success test message"
        error_msg = "Configuration error produced"

        @retry_on_error(custom_error=self.CustomError,
                        action_msg=action_msg,
                        success_msg=success_msg)
        def to_be_decorated(self):
            raise Exception(error_msg)
        with self.assertLogs("logger_dlrn", level="INFO") as cm:
            self.assertRaises(Exception, to_be_decorated, self)  # noqa: H202
            self.assertRegex(cm.output[0], action_msg)
            self.assertRegex(cm.output[1], error_msg)

    @unittest.skipIf(gssapi is None or ipalib is None,
                     "gssapi or ipalib modules not installed")
    def test_ipa_authorization_decorator_max_retries_error(self, db_mock):
        from dlrn.api.drivers.krbauthentication import retry_on_error
        action_msg = "Starting test message"
        success_msg = "Success test message"
        error_msg = "Custom error produced"

        @retry_on_error(custom_error=(self.CustomError, self.CustomError2),
                        action_msg=action_msg,
                        success_msg=success_msg)
        def to_be_decorated(self):
            raise self.CustomError(error_msg)

        @retry_on_error(custom_error=(self.CustomError, self.CustomError2),
                        action_msg=action_msg,
                        success_msg=success_msg)
        def to_be_decorated_2(self):
            raise self.CustomError2(error_msg)

        # Checking that first error type is risen 3 times
        with self.assertLogs("logger_dlrn", level="INFO") as cm:
            self.assertRaises(Exception, to_be_decorated, self)  # noqa: H202
            self.assertRegex(cm.output[0], action_msg)
            self.assertRegex(cm.output[1], error_msg)
            self.assertRegex(cm.output[-1], "Maximum retries executed")
        # Checking that second error type is risen 3 times
        with self.assertLogs("logger_dlrn", level="INFO") as cm:
            self.assertRaises(Exception, to_be_decorated_2, self)  # noqa: H202
            self.assertRegex(cm.output[0], action_msg)
            self.assertRegex(cm.output[1], error_msg)
            self.assertRegex(cm.output[-1], "Maximum retries executed")


class TestGetLogger(DLRNAPITestCase):
    log_debug_var = "LOG_LEVEL"
    log_path_var = "Path1"
    config = {}
    dlrn_logger_name = "logger_dlrn"
    auth_logger_name = "logger_auth"
    dlrn_handler_name = "file_dlrn"
    auth_handler_name = "file_auth"
    file_path = "Path1"
    log_level = "DEBUG"
    debug_bool = True

    def test_get_config_debug(self):
        self.assertEqual(get_config(self.config,
                                    self.log_debug_var), False)
        with patch.object(os.environ, 'get') as os_environ_get:
            os_environ_get.return_value = True
            self.assertEqual(get_config(self.config,
                                        self.log_debug_var), True)
            self.config[self.log_debug_var] = False
            self.assertEqual(get_config(self.config,
                                        self.log_debug_var), False)

    def test_get_config_path(self):
        self.assertEqual(get_config(self.config,
                                    self.log_path_var), False)
        with patch.object(os.environ, 'get') as os_environ_get:
            os_environ_get.return_value = "Path1"
            self.assertEqual(get_config(self.config,
                                        self.log_path_var), "Path1")
            self.config[self.log_path_var] = "Path2"
            self.assertEqual(get_config(self.config,
                                        self.log_path_var), "Path2")

    def test_create_rotating_file_handler_dict(self):
        handler_dict = create_rotating_file_handler_dict(
            self.dlrn_handler_name, self.file_path)
        result_handler_dict = mock_handler_dict(
            self.dlrn_handler_name, self.file_path)
        self.assertEqual(handler_dict, result_handler_dict)

    def test_create_logger_dict(self):
        logger_dict = create_logger_dict(self.dlrn_logger_name,
                                         self.dlrn_handler_name,
                                         self.log_level)
        result_logger_dict = mock_logger_dict(self.dlrn_logger_name,
                                              self.dlrn_handler_name,
                                              self.log_level)
        self.assertEqual(logger_dict, result_logger_dict)

    def test_setup_basic_dict_config(self):
        basic_dict_config = setup_dict_config(self.config)
        self.assertEqual(len(basic_dict_config["handlers"]), 0)
        self.assertEqual(len(basic_dict_config["loggers"]), 1)
        self.assertEqual(len(basic_dict_config["loggers"]["root"]), 1)
        # Without configuration, we want the minimum login configuration
        self.assertEqual(basic_dict_config["loggers"]["root"]['level'], 'INFO')

    @mock.patch('dlrn.api.api_logging.get_config')
    @mock.patch('dlrn.api.api_logging.get_config')
    @mock.patch('dlrn.api.api_logging.create_rotating_file_handler_dict',
                side_effect=mock_handler_dict)
    @mock.patch('dlrn.api.api_logging.create_logger_dict',
                side_effect=mock_logger_dict)
    def test_setup_complex_dict_config(self, mocked_logged_dict,
                                       mocked_handler_dict, mocked_retr_debug,
                                       mocked_retr_path):
        mocked_retr_debug.return_value = self.debug_bool
        mocked_retr_path.return_value = self.log_path_var
        result_dlrn_handler_dict = mock_handler_dict(self.dlrn_handler_name,
                                                     self.file_path)
        result_dlrn_logger_dict = mock_logger_dict(self.dlrn_logger_name,
                                                   self.dlrn_handler_name,
                                                   self.log_level,)
        result_auth_handler_dict = mock_handler_dict(self.auth_handler_name,
                                                     self.file_path)
        result_auth_logger_dict = mock_logger_dict(self.auth_logger_name,
                                                   self.auth_handler_name,
                                                   self.log_level,)
        return_dict = (setup_dict_config({}))
        return_loggers = return_dict["loggers"]
        return_handlers = return_dict["handlers"]
        self.assertDictEqual(return_loggers[self.dlrn_logger_name],
                             result_dlrn_logger_dict[self.dlrn_logger_name])
        self.assertDictEqual(return_handlers[self.dlrn_handler_name],
                             result_dlrn_handler_dict[self.dlrn_handler_name])
        self.assertDictEqual(return_loggers[self.auth_logger_name],
                             result_auth_logger_dict[self.auth_logger_name])
        self.assertDictEqual(return_handlers[self.auth_handler_name],
                             result_auth_handler_dict[self.auth_handler_name])


class TestConfigurationValidator(DLRNAPITestCase):
    krb_basic_config = {"AUTHENTICATION_DRIVERS": "['KrbAuthentication']",
                        "HTTP_KEYTAB_PATH": "http_keytab",
                        "KEYTAB_PATH": "path",
                        "KEYTAB_PRINC": "princ"}

    @mock.patch("dlrn.api.utils.ConfigurationValidator.validate_api_drivers",
                return_value=True)
    def test_validate_config(self, vt_drivers):
        config_validator = ConfigurationValidator({})
        self.assertEqual(str(config_validator), "No errors were found during"
                         " the API config validation.")
        self.assertEqual(vt_drivers.call_count, 1)

    def test_success_validate_api_roles_db(self):
        configurations = [{"API_READ_ONLY_ROLES": "Role1",
                           "API_READ_WRITE_ROLES": "Role2",
                           "DB_PATH": "path1"},
                          {"DB_PATH": "path1"}]
        for config in configurations:
            configuration_validation = ConfigurationValidator(config)
            self.assertEqual(configuration_validation.is_valid(), True)

    def test_failed_validate_api_roles_db(self):
        configurations = [{"API_READ_ONLY_ROLES": "Role1",
                           "DB_PATH": "path1"},
                          {"API_READ_WRITE_ROLES": "Role2",
                           "DB_PATH": "path1"}]
        error_section = "Section: API_ROLES_ERROR"
        error = "Declare both or none from API_READ_WRITE_ROLES "\
                "and API_READ_ONLY_ROLES."
        for config in configurations:
            configuration_validation = ConfigurationValidator(config)
            self.assertEqual(configuration_validation.is_valid(), False)
            self.assertRegex(str(configuration_validation), error_section)
            self.assertRegex(str(configuration_validation), error)

    def test_success_validate_api_roles_krb(self):
        confs = [{"API_READ_ONLY_ROLES": "Role1",
                  "API_READ_WRITE_ROLES": "Role2"},
                 {"ALLOWED_GROUP": "Role1"}]
        for config in confs:
            config.update(self.krb_basic_config)
            configuration_validation = ConfigurationValidator(config)
            self.assertEqual(configuration_validation.is_valid(), True)

    def test_failed_validate_api_roles_krb(self):
        confs = [{"API_READ_WRITE_ROLES": "Role2"},
                 {}]
        error_section = "Section: API_ROLES_ERROR"
        errors = ["Declare both or none from API_READ_WRITE_ROLES "
                  "and API_READ_ONLY_ROLES.",
                  "KrbAuthentication driver requires setting either"
                  " ALLOWED_GROUP or both API_READ_WRITE_ROLES and"
                  " API_READ_ONLY_ROLES."]
        for element in range(len(confs)):
            confs[element].update(self.krb_basic_config)
            configuration_validation = ConfigurationValidator(confs[element])
            self.assertEqual(configuration_validation.is_valid(), False)
            self.assertRegex(str(configuration_validation), error_section)
            self.assertRegex(str(configuration_validation), errors[element])

    @mock.patch("dlrn.api.utils.ConfigurationValidator."
                "validate_KrbAuthentication_driver", return_value=True)
    @mock.patch("dlrn.api.utils.ConfigurationValidator."
                "validate_dbauthentication_driver", return_value=True)
    def test_validate_api_drivers_all(self, db_driver, krb_driver):
        config = {"AUTHENTICATION_DRIVERS": "['KrbAuthentication', \
                  'DBAuthentication']"}
        ConfigurationValidator(config)
        self.assertEqual(krb_driver.call_count, 1)
        self.assertEqual(db_driver.call_count, 1)

    @mock.patch("dlrn.api.utils.ConfigurationValidator."
                "validate_KrbAuthentication_driver", return_value=True)
    @mock.patch("dlrn.api.utils.ConfigurationValidator."
                "validate_dbauthentication_driver", return_value=True)
    def test_validate_api_drivers_default(self, db_driver, krb_driver):
        ConfigurationValidator({})
        self.assertEqual(krb_driver.call_count, 0)
        self.assertEqual(db_driver.call_count, 1)

    @mock.patch("dlrn.api.utils.ConfigurationValidator."
                "validate_KrbAuthentication_driver", return_value=True)
    @mock.patch("dlrn.api.utils.ConfigurationValidator."
                "validate_dbauthentication_driver", return_value=True)
    def test_validate_api_drivers_db(self, db_driver, krb_driver):
        config = {"AUTHENTICATION_DRIVERS": "['DBAuthentication']"}
        ConfigurationValidator(config)
        self.assertEqual(krb_driver.call_count, 0)
        self.assertEqual(db_driver.call_count, 1)

    @mock.patch("dlrn.api.utils.ConfigurationValidator."
                "validate_KrbAuthentication_driver", return_value=True)
    @mock.patch("dlrn.api.utils.ConfigurationValidator."
                "validate_dbauthentication_driver", return_value=True)
    def test_validate_api_drivers_krb(self, db_driver, krb_driver):
        config = {"AUTHENTICATION_DRIVERS": "['KrbAuthentication']"}
        ConfigurationValidator(config)
        self.assertEqual(krb_driver.call_count, 1)
        self.assertEqual(db_driver.call_count, 0)

    @mock.patch("dlrn.api.utils.ConfigurationValidator.validate_api_roles",
                return_value=True)
    def test_success_validate_dbauthentication_driver(self, vt_roles):
        config = {"AUTHENTICATION_DRIVERS": "['DBAuthentication']",
                  "DB_PATH": "path1"}
        configuration_validation = ConfigurationValidator(config)
        self.assertEqual(configuration_validation.is_valid(), True)
        self.assertEqual(vt_roles.call_count, 1)

    @mock.patch("dlrn.api.utils.ConfigurationValidator.validate_api_roles",
                return_value=True)
    def test_failed_validate_dbauthentication_driver(self, vt_roles):
        config = {"AUTHENTICATION_DRIVERS": "['DBAuthentication']"}
        configuration_validation = ConfigurationValidator(config)
        error_section = "Section: DBAUTH_DRIVER_ERROR"
        error = "No DB_PATH in the app configuration."
        self.assertEqual(configuration_validation.is_valid(), False)
        self.assertRegex(str(configuration_validation), error_section)
        self.assertRegex(str(configuration_validation), error)
        self.assertEqual(vt_roles.call_count, 1)

    @mock.patch("dlrn.api.utils.ConfigurationValidator.validate_api_roles",
                return_value=True)
    def test_success_validate_krbauthentication_driver(self, vt_roles):
        config = {"AUTHENTICATION_DRIVERS": "['KrbAuthentication']",
                  "HTTP_KEYTAB_PATH": "http_keytab", "KEYTAB_PATH": "path",
                  "KEYTAB_PRINC": "princ"}
        configuration_validation = ConfigurationValidator(config)
        self.assertEqual(configuration_validation.is_valid(), True)
        self.assertEqual(vt_roles.call_count, 1)

    @mock.patch("dlrn.api.utils.ConfigurationValidator.validate_api_roles",
                return_value=True)
    def test_failed_validate_krbauthentication_driver(self, vt_roles):
        config = {"AUTHENTICATION_DRIVERS": "['KrbAuthentication']"}
        error_section = "Section: KRBAUTH_DRIVER_ERROR"
        error_http_keytab_path = "No HTTP_KEYTAB_PATH in the app " \
                                 "configuration."
        error_keytab_path = "No KEYTAB_PATH in the app configuration."
        error_keytab_princ = "No KEYTAB_PRINC in the app configuration."
        configuration_validation = ConfigurationValidator(config)
        self.assertEqual(configuration_validation.is_valid(), False)
        self.assertRegex(str(configuration_validation), error_section)
        self.assertRegex(str(configuration_validation), error_http_keytab_path)
        self.assertRegex(str(configuration_validation), error_keytab_path)
        self.assertRegex(str(configuration_validation), error_keytab_princ)
        self.assertEqual(vt_roles.call_count, 1)
