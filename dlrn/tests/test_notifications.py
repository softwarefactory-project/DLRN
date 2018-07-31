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
import shutil
import tempfile

from dlrn.config import ConfigOptions
from dlrn import db
from dlrn import notifications
from dlrn.tests import base
from six.moves import configparser


class TestNotifications(base.TestCase):
    def setUp(self):
        super(TestNotifications, self).setUp()
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'datadir', tempfile.mkdtemp())
        config.set('DEFAULT', 'scriptsdir', tempfile.mkdtemp())
        config.set('DEFAULT', 'baseurl', "file://%s" % config.get('DEFAULT',
                                                                  'datadir'))

        self.config = ConfigOptions(config)
        self.commit = db.Commit(dt_commit=123, project_name='foo',
                                commit_hash='1c67b1ab8c6fe273d4e175a14f0df5'
                                            'd3cbbd0edf',
                                repo_dir='/home/dlrn/data/foo',
                                distro_hash='c31d1b18eb5ab5aed6721fc4fad06c9'
                                            'bd242490f',
                                dt_distro=123,
                                distgit_dir='/home/dlrn/data/foo_distro',
                                commit_branch='master', dt_build=1441245153)
        self.packages = [{'upstream': 'https://github.com/openstack/foo',
                          'name': 'foo', 'maintainers': ['test@test.com'],
                          'master-distgit':
                          'https://github.com/rdo-packages/foo-distgit.git'}]

    def tearDown(self):
        super(TestNotifications, self).tearDown()
        shutil.rmtree(self.config.datadir)
        shutil.rmtree(self.config.scriptsdir)

    @mock.patch('sh.env', create=True)
    def test_submit_review(self, sh_mock):
        notifications.submit_review(self.commit, self.packages, ['FOO=BAR'])
        yumdir = os.path.join(self.config.datadir, 'repos',
                              self.commit.getshardedcommitdir())

        expected = [mock.call(['FOO=BAR', 'GERRIT_URL=https://github.com/'
                                          'openstack/foo/commit/' +
                                          self.commit.commit_hash,
                               'GERRIT_LOG=%s/%s' % (
                                   self.config.baseurl,
                                   self.commit.getshardedcommitdir()
                               ),
                               'GERRIT_MAINTAINERS=test@test.com',
                               'GERRIT_TOPIC=rdo-FTBFS',
                               os.path.join(self.config.scriptsdir,
                                            "submit_review.sh"),
                    self.commit.project_name, yumdir, self.config.datadir,
                    self.config.baseurl,
                    os.path.realpath(self.commit.distgit_dir)],
                    _timeout=300)]

        self.assertEqual(sh_mock.call_count, 1)
        self.assertEqual(sh_mock.call_args_list, expected)

    @mock.patch('smtplib.SMTP', create=True)
    def test_sendnotifymail_nomail(self, smtp_mock):
        notifications.sendnotifymail(self.packages, self.commit)
        # By default there is no smtpserver, so no calls
        self.assertEqual(smtp_mock.call_count, 0)

    @mock.patch('smtplib.SMTP', create=True)
    def test_sendnotifymail(self, smtp_mock):
        self.config.smtpserver = 'foo.example.com'
        notifications.sendnotifymail(self.packages, self.commit)
        self.assertEqual(smtp_mock.call_count, 1)
