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
import sh
import sys
import urllib2

from dlrn.tests import base

from dlrn import db
from dlrn import remote
from dlrn import utils


def mocked_session(url):
    session = db.getSession(new=True)
    utils.loadYAML(session, './dlrn/tests/samples/commits_1.yaml')
    return session


def mocked_urlopen(url):
    if url.startswith('http://example.com'):
        fp = open('./dlrn/tests/samples/commits_remote.yaml', 'r')
        return fp
    else:
        return urllib2.urlopen(url)


@mock.patch.object(sh.Command, '__call__', autospec=True)
@mock.patch('dlrn.remote.post_build')
@mock.patch('dlrn.remote.getSession', side_effect=mocked_session)
@mock.patch('urllib2.urlopen', side_effect=mocked_urlopen)
class TestRemote(base.TestCase):
    def test_remote(self, url_mock, db_mock, build_mock, sh_mock):
        testargs = ["dlrn-remote", "--config-file", "projects.ini",
                    "--repo-url", "http://example.com/1/"]
        # There should be only one call to post_build(), even though there are
        # 2 commits in the commits_remote.yaml file. This is because the first
        # one is already in the database
        with mock.patch.object(sys, 'argv', testargs):
            remote.remote()
            build_mock.assert_called_once()
