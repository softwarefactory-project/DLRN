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
from dlrn.config import ConfigOptions
from dlrn import db
from dlrn.tests import base
from dlrn import utils
from six.moves import configparser


def mocked_session(url):
    db_fd, filepath = tempfile.mkstemp()
    session = db.getSession("sqlite:///%s" % filepath)
    utils.loadYAML(session, './dlrn/tests/samples/commits_1.yaml')
    return session


def mock_opt(config_file):
    cp = configparser.RawConfigParser()
    cp.read(config_file)
    co = ConfigOptions(cp)
    co.baseurl = 'http://localhost/worker'
    return co


class DLRNPrometheusMetricsTestCase(base.TestCase):
    def setUp(self):
        super(DLRNPrometheusMetricsTestCase, self).setUp()
        self.db_fd, self.filepath = tempfile.mkstemp()
        app.config['DB_PATH'] = "sqlite:///%s" % self.filepath
        app.config['REPO_PATH'] = '/tmp'
        self.app = app.test_client()
        self.app.testing = True

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.filepath)
        super(DLRNPrometheusMetricsTestCase, self).tearDown()


@mock.patch('dlrn.api.prom_metrics._get_config_options', side_effect=mock_opt)
@mock.patch('dlrn.api.prom_metrics.getSession', side_effect=mocked_session)
class TestBasic(DLRNPrometheusMetricsTestCase):
    def test_query(self, db_mock, co_mock):
        response = self.app.get('/metrics')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/plain')

    def test_successful_buidls(self, db_mock, co_mock):
        response = self.app.get('/metrics')
        self.assertEqual(response.status_code, 200)
        # commits_1.yaml has 13 commits in SUCCESS state,
        # 5 in RETRY and 5 in FAILED
        self.assertIn('dlrn_builds_succeeded_total{baseurl="http://'
                      'localhost/worker"} 15.0', response.data.decode())
        self.assertIn('dlrn_builds_failed_total{baseurl='
                      '"http://localhost/worker"} 5.0', response.data.decode())
        self.assertIn('dlrn_builds_retry_total{baseurl='
                      '"http://localhost/worker"} 5.0', response.data.decode())
        self.assertIn('dlrn_builds_total{baseurl="http://'
                      'localhost/worker"} 25.0', response.data.decode())
