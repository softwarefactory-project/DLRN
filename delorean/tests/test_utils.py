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
from mock import call
from mock import MagicMock

from delorean import db
from delorean.tests.test_db import TestsWithData
from delorean import utils


class Testdumpshas2file(TestsWithData):
    def test_noretry(self):
        # SUCCESS
        commit = db.getLastProcessedCommit(self.session, 'python-pysaml2')
        # FAILED
        commit2 = db.getLastProcessedCommit(self.session, 'python-alembic')
        # SUCCESS, RETRY (should be ignored)
        commit3 = \
            db.getLastProcessedCommit(self.session, 'python-tripleoclient')

        mock_fp = MagicMock()
        utils.dumpshas2file(mock_fp, commit, "a", "b", commit.status, 0)
        utils.dumpshas2file(mock_fp, commit2, "a", "b", commit2.status, 1)
        utils.dumpshas2file(mock_fp, commit3, "a", "b", commit3.status, 2)
        expected = [
            call.write(u'python-pysaml2,a,3a9326f251b9a4162eb0dfa9f1c924ef47c'
                       '2c55a,b,024e24f0cf4366c2290c22f24e42de714d1addd1'
                       ',SUCCESS,0\n'),
            call.write(u'python-alembic,a,459549c9ab7fef91b2dc8986bc0643bb2f6'
                       'ec0c8,b,885e80778edb6cbb8ee4d8909623be8062369a04'
                       ',FAILED,1\n'),
            call.write(u'python-tripleoclient,a,1da7b10e55abf8c518e8f61ee7966'
                       '188f0405f59,b,0b1ce934e5b2e7d45a448f6555d24036f9aeca51'
                       ',SUCCESS,2\n')
        ]
        self.assertEqual(mock_fp.mock_calls, expected)
