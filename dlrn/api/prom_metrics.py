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

from dlrn.api import app
from dlrn.config import ConfigOptions
from dlrn.db import closeSession
from dlrn.db import Commit
from dlrn.db import getSession

from flask import g
from flask import Response

from prometheus_client.core import CounterMetricFamily
from prometheus_client.core import REGISTRY
from prometheus_client import generate_latest
from prometheus_client import Summary

from six.moves import configparser


# Create a metric to track time spent and requests made.
REQUEST_TIME = Summary('dlrn_request_processing_seconds',
                       'Time spent processing request')


def _get_db():
    if 'db' not in g:
        g.db = getSession(app.config['DB_PATH'])
    return g.db


def _get_config_options(config_file):
    cp = configparser.RawConfigParser()
    cp.read(config_file)
    return ConfigOptions(cp)


class DLRNPromCollector(object):
    @REQUEST_TIME.time()
    def collect(self):
        config_options = _get_config_options(app.config['CONFIG_FILE'])
        c_success = CounterMetricFamily('dlrn_builds_succeeded',
                                        'Total number of successful builds',
                                        labels=['baseurl'])
        c_failed = CounterMetricFamily('dlrn_builds_failed',
                                       'Total number of failed builds',
                                       labels=['baseurl'])
        c_retry = CounterMetricFamily('dlrn_builds_retry',
                                      'Total number of builds in retry state',
                                      labels=['baseurl'])
        c_overall = CounterMetricFamily('dlrn_builds',
                                        'Total number of builds',
                                        labels=['baseurl'])

        # Find the commits count for each metric
        with app.app_context():
            session = _get_db()
            successful_commits = session.query(Commit).filter(
                Commit.status == 'SUCCESS').count()
            failed_commits = session.query(Commit).filter(
                Commit.status == 'FAILED').count()
            retried_commits = session.query(Commit).filter(
                Commit.status == 'RETRY').count()
            all_commits = session.query(Commit).count()

            c_success.add_metric([config_options.baseurl], successful_commits)
            c_failed.add_metric([config_options.baseurl], failed_commits)
            c_retry.add_metric([config_options.baseurl], retried_commits)
            c_overall.add_metric([config_options.baseurl], all_commits)

        return [c_success, c_failed, c_retry, c_overall]


REGISTRY.register(DLRNPromCollector())


@app.route('/metrics', methods=['GET'])
def prom_metrics():
    return Response(generate_latest(), mimetype='text/plain')


@app.teardown_appcontext
def teardown_db(exception=None):
    session = g.pop('db', None)
    if session is not None:
        closeSession(session)
