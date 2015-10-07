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
import sqlalchemy

from delorean import db
from delorean import tests


@mock.patch.object(sqlalchemy.orm.sessionmaker, '__call__', autospec=True)
class TestGetSessions(tests.base.TestCase):
    def setUp(self):
        super(TestGetSessions, self).setUp()
        db._sessions = {}

    def test_getsession(self, sm_mock):
        db.getSession()
        self.assertEqual(len(sm_mock.call_args_list), 1)

    @mock.patch('sqlalchemy.create_engine')
    def test_getsessions(self, ce_mock, sm_mock):
        db.getSession()
        db.getSession(url="sqlite:///test.db")
        # The 2nd call shouldn't result in a new session
        db.getSession()
        self.assertEqual(len(sm_mock.call_args_list), 2)
        expected = [mock.call('sqlite://'),
                    mock.call('sqlite:///test.db')]
        self.assertEqual(ce_mock.call_args_list, expected)
