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
import shutil
import sys
import tempfile
import time

from dlrn.tests import base

from datetime import datetime
from dlrn import db
from dlrn import purge
from dlrn import utils
from six.moves import configparser

expected_repos = [
    './data/repos/ae/9d/ae9d27e5100f002f55ad6eb2b252a0aa5f16a336_024e24f0',
    './data/repos/45/95/459549c9ab7fef91b2dc8986bc0643bb2f6ec0c8_885e8077',
    './data/repos/e4/f7/e4f71ada86ee4a42287cf401b77d48c9f98ca5aa_354991d9',
    './data/repos/80/f6/80f6969520b526b01c210b1c680565bef8a1f8ad_024e24f0',
    './data/repos/12/ed/12edde8a53c7299105bb8297c6f31d3a458615ab_354991d9',
    './data/repos/17/23/17234e9ab9dfab4cf5600f67f1d24db5064f1025_024e24f0']


def mocked_session(url):
    db_fd, filepath = tempfile.mkstemp()
    session = db.getSession("sqlite:///%s" % filepath)
    utils.loadYAML(session, './dlrn/tests/samples/commits_1.yaml')
    return session


def mocked_session_2(url):
    db_fd, filepath = tempfile.mkstemp()
    session = db.getSession("sqlite:///%s" % filepath)
    utils.loadYAML(session, './dlrn/tests/samples/commits_2.yaml')
    return session


def mocked_listdir(path):
    return ['file1.rpm', 'file2.rpm', 'file3.rpm']


def mocked_islink(path):
    return False


def mocked_is_commit_in_dirs(commit, dirlist, basedir, component_list=None):
    # We are making one of the commit hashes be in the excluded dir list
    if commit.commit_hash == '6abf557aa1d8fff0aa21f8eba6cd18302c2c86ff':
        return True
    return False


def mocked_exists_false(path):
    return False


@mock.patch('os.path.islink', side_effect=mocked_islink)
@mock.patch('os.listdir', side_effect=mocked_listdir)
@mock.patch('dlrn.purge.getSession', side_effect=mocked_session)
@mock.patch('shutil.rmtree')
@mock.patch('dlrn.purge.is_commit_in_dirs',
            side_effect=mocked_is_commit_in_dirs)
class TestPurge(base.TestCase):
    @mock.patch('dlrn.purge.datetime')
    def test_purge(self, dt_mock, icid_mock, sh_mock, db_mock, lst_mock,
                   il_mock):
        testargs = ["dlrn-purge", "--config-file",
                    "projects.ini", "--older-than",
                    "1", "-y"]
        dt_mock.now.return_value = datetime(2015, 10, 1, 14, 20)
        with mock.patch.object(sys, 'argv', testargs):
            purge.purge()
            expected = []
            for repo in expected_repos:
                expected.append(mock.call(repo, ignore_errors=True))
            self.assertEqual(sh_mock.call_args_list, expected)


@mock.patch('os.path.exists', side_effect=mocked_exists_false)
class TestIsCommitInDirs(base.TestCase):
    def test_is_commit_in_dirs_component(self, ex_mock):
        commit = db.Commit(dt_commit=123, project_name='foo', type="rpm",
                           component='bar',
                           commit_hash='1c67b1ab8c6fe273d4e175a14f0df5'
                                       'd3cbbd0edf',
                           repo_dir='/home/dlrn/data/foo',
                           distro_hash='c31d1b18eb5ab5aed6721fc4fad06c9'
                                       'bd242490f',
                           dt_distro=123,
                           distgit_dir='/home/dlrn/data/foo_distro',
                           commit_branch='master', dt_build=1441245153,
                           artifacts='foo-1.0.0.rpm')

        dirlist = ('/home/dlrn/data/repos/consistent,'
                   '/home/dlrn/data/repos/foo-ci')
        basedir = '/home/dlrn/data/repos/'
        expected = [mock.call('/home/dlrn/data/repos/consistent/'
                              'foo-1.0.0.rpm'),
                    mock.call('/home/dlrn/data/repos/component/bar/consistent/'
                              'foo-1.0.0.rpm'),
                    mock.call('/home/dlrn/data/repos/foo-ci/'
                              'foo-1.0.0.rpm'),
                    mock.call('/home/dlrn/data/repos/component/bar/foo-ci/'
                              'foo-1.0.0.rpm')]

        purge.is_commit_in_dirs(commit, dirlist, basedir,
                                component_list=['bar'])

        self.assertEqual(ex_mock.call_args_list, expected)


@mock.patch('shutil.rmtree')
@mock.patch('dlrn.purge.getSession', side_effect=mocked_session_2)
class TestAggPurge(base.TestCase):
    def setUp(self):
        super(TestAggPurge, self).setUp()
        self.config = configparser.RawConfigParser()
        self.config.read("projects.ini")
        self.temp_dir = tempfile.mkdtemp()
        self.config.set('DEFAULT', 'datadir', self.temp_dir)
        os.makedirs(os.path.join(self.temp_dir, 'repos',
                                 'another-ci/12/34/12345678'))
        os.makedirs(os.path.join(self.temp_dir, 'repos',
                                 'foo-ci/90/ab/90abcdef'))

    def tearDown(self):
        super(TestAggPurge, self).tearDown()
        shutil.rmtree(self.temp_dir)

    def test_purge_promoted(self, db_mock, rm_mock):
        purge.purge_promoted_hashes(self.config, time.time(), dry_run=False)
        self.assertEqual(rm_mock.call_count, 2)

    def test_purge_promoted_only_one(self, db_mock, rm_mock):
        current_time = time.time()
        time.sleep(1)
        # Update modification time on one of the dirs
        os.utime(os.path.join(self.temp_dir, 'repos',
                              'foo-ci/90/ab/90abcdef'), None)
        purge.purge_promoted_hashes(self.config, current_time, dry_run=False)
        self.assertEqual(rm_mock.call_count, 1)

    def test_purge_promoted_dry_run(self, db_mock, rm_mock):
        purge.purge_promoted_hashes(self.config, time.time(), dry_run=True)
        self.assertEqual(rm_mock.call_count, 0)

    def test_purge_promoted_protected_path(self, db_mock, rm_mock):
        orig_path = os.path.join(self.temp_dir, 'repos',
                                 'foo-ci/90/ab/90abcdef', 'delorean.repo')
        dst_path = os.path.join(self.temp_dir, 'repos', 'foo-ci/delorean.repo')
        os.symlink(orig_path, dst_path)
        purge.purge_promoted_hashes(self.config, time.time(), dry_run=False)
        self.assertEqual(rm_mock.call_count, 1)
