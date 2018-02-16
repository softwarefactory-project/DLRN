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
import os
import passlib.hash
import sys
import tempfile

from dlrn import db
from dlrn.tests import base
from dlrn import user
from dlrn import utils


class TestUser(base.TestCase):
    def setUp(self):
        super(TestUser, self).setUp()
        self.db_fd, filepath = tempfile.mkstemp()
        self.session = db.getSession("sqlite:///%s" % filepath)
        utils.loadYAML(self.session, './dlrn/tests/samples/commits_2.yaml')

    def tearDown(self):
        super(TestUser, self).tearDown()
        os.close(self.db_fd)

    def mocked_session(url):
        return self.session

    @mock.patch('dlrn.user.getSession')
    def test_user_create(self, db_mock):
        db_mock.return_value = self.session
        testargs = ["dlrn-user", "create", "--username",
                    "user", "--password", "password"]
        with mock.patch.object(sys, 'argv', testargs):
            user.user_manager()

        # Now check that the user was created
        myuser = self.session.query(db.User).filter(
            db.User.username == 'user').first()
        self.assertEqual(myuser.username, 'user')

    @mock.patch('dlrn.user.getSession')
    def test_user_create_duplicate(self, db_mock):
        db_mock.return_value = self.session
        testargs = ["dlrn-user", "create", "--username",
                    "user", "--password", "password"]
        with mock.patch.object(sys, 'argv', testargs):
            user.user_manager()
            return_value = user.user_manager()

        # Check that we got a failure
        self.assertEqual(return_value, -1)

    @mock.patch('dlrn.user.getpass')
    @mock.patch('dlrn.user.getSession')
    def test_user_create_interactive(self, db_mock, gp_mock):
        db_mock.return_value = self.session
        gp_mock.return_value = 'password'
        testargs = ["dlrn-user", "create", "--username", "user"]
        with mock.patch.object(sys, 'argv', testargs):
            user.user_manager()

        # Now check that the user was created
        myuser = self.session.query(db.User).filter(
            db.User.username == 'user').first()
        self.assertEqual(myuser.username, 'user')

    @mock.patch('dlrn.user.getSession')
    def test_user_update(self, db_mock):
        db_mock.return_value = self.session
        testargs = ["dlrn-user", "update", "--username",
                    "foo", "--password", "password"]
        with mock.patch.object(sys, 'argv', testargs):
            user.user_manager()

        # Now check that the user was properly updated
        myuser = self.session.query(db.User).filter(
            db.User.username == 'foo').first()
        self.assertEqual(
            passlib.hash.sha512_crypt.verify('password', myuser.password),
            True)

    @mock.patch('dlrn.user.getSession')
    def test_user_update_non_existing(self, db_mock):
        db_mock.return_value = self.session
        testargs = ["dlrn-user", "update", "--username", "noone",
                    "--password", "foo"]
        with mock.patch.object(sys, 'argv', testargs):
            return_value = user.user_manager()

        # Check that we got a failure
        self.assertEqual(return_value, -1)

    @mock.patch('dlrn.user.getSession')
    def test_user_delete_force(self, db_mock):
        db_mock.return_value = self.session
        testargs = ["dlrn-user", "create", "--username",
                    "user2", "--password", "password"]
        with mock.patch.object(sys, 'argv', testargs):
            user.user_manager()

        testargs = ["dlrn-user", "delete", "--username",
                    "user2", "--force"]
        with mock.patch.object(sys, 'argv', testargs):
            user.user_manager()

        # Now check that the user was deleted
        myuser = self.session.query(db.User).filter(
            db.User.username == 'user2').first()
        self.assertEqual(myuser, None)

    @mock.patch('dlrn.user.input')
    @mock.patch('dlrn.user.getSession')
    def test_user_delete_confirm(self, db_mock, in_mock):
        db_mock.return_value = self.session
        in_mock.return_value = 'YES'
        testargs = ["dlrn-user", "create", "--username",
                    "user3", "--password", "password"]
        with mock.patch.object(sys, 'argv', testargs):
            user.user_manager()

        testargs = ["dlrn-user", "delete", "--username", "user3"]
        with mock.patch.object(sys, 'argv', testargs):
            user.user_manager()

        # Now check that the user was deleted
        myuser = self.session.query(db.User).filter(
            db.User.username == 'user3').first()
        self.assertEqual(myuser, None)

    @mock.patch('dlrn.user.input')
    @mock.patch('dlrn.user.getSession')
    def test_user_delete_without_confirm(self, db_mock, in_mock):
        db_mock.return_value = self.session
        in_mock.return_value = 'abc'
        testargs = ["dlrn-user", "create", "--username",
                    "user4", "--password", "password"]
        with mock.patch.object(sys, 'argv', testargs):
            user.user_manager()

        testargs = ["dlrn-user", "delete", "--username", "user4"]
        with mock.patch.object(sys, 'argv', testargs):
            user.user_manager()

        # Now check that the user was deleted
        myuser = self.session.query(db.User).filter(
            db.User.username == 'user4').first()
        self.assertNotEqual(myuser, None)

    @mock.patch('dlrn.user.getSession')
    def test_user_delete_non_existing(self, db_mock):
        db_mock.return_value = self.session
        testargs = ["dlrn-user", "delete", "--username", "noone"]
        with mock.patch.object(sys, 'argv', testargs):
            return_value = user.user_manager()

        # Check that we got a failure
        self.assertEqual(return_value, -1)
