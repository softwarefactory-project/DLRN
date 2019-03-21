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

from dlrn.config import ConfigOptions
from dlrn import repositories
from dlrn.tests import base

from six.moves import configparser


def _aux_sh(*args):
    call = args[0]
    if call == '-f':
        raise sh.ErrorReturnCode_1('blabla'.encode(), ''.encode(),
                                   ''.encode())
    return


@mock.patch.object(sh.Command, '__call__', autospec=True)
class TestRefreshRepo(base.TestCase):

    def test_clone_if_not_cloned(self, sh_mock):
        repositories.refreshrepo('url', 'path', branch='branch')
        expected = [mock.call(sh.git.clone, 'url', 'path'),
                    mock.call(sh.git.fetch, 'origin'),
                    mock.call(sh.git.checkout, '-f', 'branch'),
                    mock.call(sh.git.reset, '--hard', 'origin/branch'),
                    mock.call(sh.git.log, '--pretty=format:%H %ct', '-1', '.')]
        self.assertEqual(sh_mock.call_args_list, expected)

    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('shutil.rmtree', return_value=True)
    def test_dont_clone_if_cloned(self, path_mock, shutil_mock, sh_mock):
        repositories.refreshrepo('url', 'path', branch='branch')
        expected = [mock.call(sh.git, 'remote', '-v'),
                    mock.call(sh.git.clone, 'url', 'path'),
                    mock.call(sh.git.fetch, 'origin'),
                    mock.call(sh.git.checkout, '-f', 'branch'),
                    mock.call(sh.git.reset, '--hard', 'origin/branch'),
                    mock.call(sh.git.log, '--pretty=format:%H %ct', '-1', '.')]
        self.assertEqual(sh_mock.call_args_list, expected)

    @mock.patch('os.path.exists', return_value=True)
    def test_dont_fetch_if_local_repo_exists(self, path_mock, sh_mock):
        repositories.refreshrepo('url', 'path', branch='branch', local=True)
        expected = [mock.call(sh.git.log, '--pretty=format:%H %ct', '-1', '.')]
        self.assertEqual(sh_mock.call_args_list, expected)

    def test_clone_fetch_if_local_repo_missing(self, sh_mock):
        repositories.refreshrepo('url', 'path', branch='branch', local=True)
        expected = [mock.call(sh.git.clone, 'url', 'path'),
                    mock.call(sh.git.fetch, 'origin'),
                    mock.call(sh.git.checkout, '-f', 'branch'),
                    mock.call(sh.git.reset, '--hard', 'origin/branch'),
                    mock.call(sh.git.log, '--pretty=format:%H %ct', '-1', '.')]
        self.assertEqual(sh_mock.call_args_list, expected)

    def test_clone_no_fallback(self, sh_mock):
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'fallback_to_master', '0')
        self.config = ConfigOptions(config)
        # We need to redefine the mock object again, to use a side effect
        # that will fail in the git checkout call. A bit convoluted, but
        # it works
        with mock.patch.object(sh.Command, '__call__') as new_mock:
            new_mock.side_effect = _aux_sh
            self.assertRaises(sh.ErrorReturnCode_1, repositories.refreshrepo,
                              'url', 'path', branch='branch')
            expected = [mock.call('url', 'path'),
                        mock.call('origin'),
                        mock.call('-f', 'branch')]
            self.assertEqual(new_mock.call_args_list, expected)

    def test_clone_no_fallback_default(self, sh_mock):
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'fallback_to_master', '1')
        self.config = ConfigOptions(config)
        with mock.patch.object(sh.Command, '__call__') as new_mock:
            new_mock.side_effect = _aux_sh
            self.assertRaises(sh.ErrorReturnCode_1, repositories.refreshrepo,
                              'url', 'path', branch='rpm-master')
            expected = [mock.call('url', 'path'),
                        mock.call('origin'),
                        mock.call('-f', 'rpm-master')]
            self.assertEqual(new_mock.call_args_list, expected)

    def test_clone_no_fallback_var(self, sh_mock):
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'fallback_to_master', '1')
        config.set('DEFAULT', 'nonfallback_branches', '^foo-')
        self.config = ConfigOptions(config)
        with mock.patch.object(sh.Command, '__call__') as new_mock:
            new_mock.side_effect = _aux_sh
            self.assertRaises(sh.ErrorReturnCode_1, repositories.refreshrepo,
                              'url', 'path', branch='foo-bar')
            expected = [mock.call('url', 'path'),
                        mock.call('origin'),
                        mock.call('-f', 'foo-bar')]
            self.assertEqual(new_mock.call_args_list, expected)

    def test_clone_fallback_var(self, sh_mock):
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'fallback_to_master', '1')
        config.set('DEFAULT', 'nonfallback_branches', '^foo-')
        self.config = ConfigOptions(config)
        with mock.patch.object(sh.Command, '__call__') as new_mock:
            new_mock.side_effect = _aux_sh
            result = repositories.refreshrepo('url', 'path', branch='bar')
            self.assertEqual(result, ['master', 'None'])
            expected = [mock.call('url', 'path'),
                        mock.call('origin'),
                        mock.call('-f', 'bar'),
                        mock.call('master'),
                        mock.call('--hard', 'origin/master'),
                        mock.call('--pretty=format:%H %ct', '-1', '.')]
            self.assertEqual(new_mock.call_args_list, expected)
