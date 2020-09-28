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
from dlrn import rsync
from dlrn.tests import base
from six.moves import configparser


@mock.patch('sh.rsync', create=True)
class TestSyncRepo(base.TestCase):
    def setUp(self):
        super(TestSyncRepo, self).setUp()
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'datadir', tempfile.mkdtemp())
        config.set('DEFAULT', 'scriptsdir', tempfile.mkdtemp())
        config.set('DEFAULT', 'baseurl', "file://%s" % config.get('DEFAULT',
                                                                  'datadir'))
        config.set('DEFAULT', 'rsyncport', '30000')
        config.set('DEFAULT', 'rsyncdest', 'user@host:/directory')

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

    def tearDown(self):
        super(TestSyncRepo, self).tearDown()
        shutil.rmtree(self.config.datadir)
        shutil.rmtree(self.config.scriptsdir)

    def test_sync_repo(self, sh_mock):
        yumdir = os.path.join(self.config.datadir, 'repos', '.',
                              self.commit.getshardedcommitdir())
        repodir = os.path.join(self.config.datadir, 'repos', '.')

        rsync.sync_repo(self.commit)
        expected = [mock.call('-avzR', '--delete-delay', '-e',
                              'ssh -p 30000 -o StrictHostKeyChecking=no',
                              [yumdir,
                               os.path.join(repodir, 'report.html'),
                               os.path.join(repodir, 'status_report.html'),
                               os.path.join(repodir, 'styles.css'),
                               os.path.join(repodir, 'queue.html'),
                               os.path.join(repodir, 'status_report.csv')],
                              'user@host:/directory')]
        self.assertEqual(sh_mock.call_args_list, expected)

    def test_sync_repo_component(self, sh_mock):
        self.commit.component = 'foocomp'
        self.config.use_components = True
        yumdir = os.path.join(self.config.datadir, 'repos', '.',
                              self.commit.getshardedcommitdir())
        repodir = os.path.join(self.config.datadir, 'repos', '.')

        rsync.sync_repo(self.commit)
        expected = [mock.call('-avzR', '--delete-delay', '-e',
                              'ssh -p 30000 -o StrictHostKeyChecking=no',
                              [yumdir,
                               os.path.join(repodir, 'report.html'),
                               os.path.join(repodir, 'status_report.html'),
                               os.path.join(repodir, 'styles.css'),
                               os.path.join(repodir, 'queue.html'),
                               os.path.join(repodir, 'status_report.csv')],
                              'user@host:/directory')]
        self.assertEqual(sh_mock.call_args_list, expected)

    def test_sync_symlinks(self, sh_mock):
        repodir = os.path.join(self.config.datadir, 'repos', '.')

        rsync.sync_symlinks(self.commit)
        expected = [mock.call('-avzR', '--delete-delay', '-e',
                              'ssh -p 30000 -o StrictHostKeyChecking=no',
                              [os.path.join(repodir, 'consistent'),
                               os.path.join(repodir, 'current')],
                              'user@host:/directory')]
        self.assertEqual(sh_mock.call_args_list, expected)

    def test_sync_symlinks_component(self, sh_mock):
        self.commit.component = 'foocomp'
        self.config.use_components = True
        repodir = os.path.join(self.config.datadir, 'repos', '.')

        rsync.sync_symlinks(self.commit)
        expected = [mock.call('-avzR', '--delete-delay', '-e',
                              'ssh -p 30000 -o StrictHostKeyChecking=no',
                              ['--exclude', 'consistent/delorean.repo',
                               '--exclude', 'consistent/delorean.repo.md5',
                               '--exclude', 'consistent/versions.csv',
                               '--exclude', 'current/delorean.repo',
                               '--exclude', 'current/delorean.repo.md5',
                               '--exclude', 'current/versions.csv'],
                              [os.path.join(repodir, 'component/foocomp',
                                            'consistent'),
                               os.path.join(repodir, 'component/foocomp',
                                            'current'),
                               os.path.join(repodir, 'consistent'),
                               os.path.join(repodir, 'current')],
                              'user@host:/directory'),
                    mock.call('-avzR', '--delete-delay', '-e',
                              'ssh -p 30000 -o StrictHostKeyChecking=no',
                              ['%s/delorean.repo' %
                               os.path.join(repodir, 'consistent'),
                               '%s/delorean.repo.md5' %
                               os.path.join(repodir, 'consistent'),
                               '%s/versions.csv' %
                               os.path.join(repodir, 'consistent'),
                               '%s/delorean.repo' %
                               os.path.join(repodir, 'current'),
                               '%s/delorean.repo.md5' %
                               os.path.join(repodir, 'current'),
                               '%s/versions.csv' %
                               os.path.join(repodir, 'current')],
                              'user@host:/directory')]
        self.assertEqual(sh_mock.call_args_list, expected)
