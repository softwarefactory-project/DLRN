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


def _aux_git_checkout(*args):
    # Accessed when call git checkout
    if args[0] == '-f':
        raise sh.ErrorReturnCode_1('blabla'.encode(), ''.encode(),
                                   ''.encode())


def _aux_git_tag(*args):
    # Accessed when call git tag
    if args[0] == '-l' and args[1] == 'branchless-eol':
        return None
    if args[0] == '-l' and args[1] == 'eoled-eol':
        return 'eoled-eol'


def _aux_git_branch(*args):
    # Accessed when call git branch
    if args[0] == '--list' and args[1] == 'master':
        return 'master'
    if args[0] == '--list' and args[1] == 'main':
        return 'main'


def _aux_git_branch_main(*args):
    # Accessed when call git branch
    if args[0] == '--list' and args[1] == 'master':
        return None
    if args[0] == '--list' and args[1] == 'main':
        return 'main'


@mock.patch('sh.git', create=True)
class TestRefreshRepo(base.TestCase):
    def setUp(self):
        super(TestRefreshRepo, self).setUp()
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set("DEFAULT", "build_driver",
                   "dlrn.drivers.mockdriver.MockBuildDriver")
        self.config = ConfigOptions(config)

    @mock.patch('os.path.exists', return_value=False)
    def test_clone_if_not_cloned(self, path_mock, git_mock):
        repositories.refreshrepo('url', 'path', self.config, branch='branch')
        expected_git_clone = [mock.call.clone('url', 'path')]
        expected_git_fetch = [mock.call.fetch('origin')]
        expected_git_checkout = [mock.call.bake().checkout('-f', 'branch')]
        expected_git_reset = [mock.call.bake().reset('--hard',
                                                     'origin/branch')]
        expected_git_log = [mock.call.bake().log('--pretty=format:%H %ct',
                                                 '-1', '.')]

        self.assertEqual(git_mock.clone.call_args_list, expected_git_clone)
        self.assertEqual(git_mock.bake().fetch.call_args_list,
                         expected_git_fetch)
        self.assertEqual(git_mock.bake().checkout.call_args_list,
                         expected_git_checkout)
        self.assertEqual(git_mock.bake().reset.call_args_list,
                         expected_git_reset)
        self.assertEqual(git_mock.bake().log.call_args_list, expected_git_log)

    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('shutil.rmtree', return_value=True)
    def test_dont_clone_if_cloned(self, path_mock, shutil_mock, git_mock):
        repositories.refreshrepo('url', 'path', self.config, branch='branch')
        expected_git_remote = [mock.call.bake()('remote', '-v')]
        expected_git_clone = [mock.call.clone('url', 'path')]
        expected_git_fetch = [mock.call.bake().fetch('origin')]
        expected_git_checkout = [mock.call.bake().checkout('-f', 'branch')]
        expected_git_reset = [mock.call.bake().reset('--hard',
                                                     'origin/branch')]
        expected_git_log = [mock.call.bake().log('--pretty=format:%H %ct',
                                                 '-1', '.')]

        self.assertEqual(git_mock.bake().call_args_list, expected_git_remote)
        self.assertEqual(git_mock.clone.call_args_list, expected_git_clone)
        self.assertEqual(git_mock.bake().fetch.call_args_list,
                         expected_git_fetch)
        self.assertEqual(git_mock.bake().checkout.call_args_list,
                         expected_git_checkout)
        self.assertEqual(git_mock.bake().reset.call_args_list,
                         expected_git_reset)
        self.assertEqual(git_mock.bake().log.call_args_list, expected_git_log)

    @mock.patch('os.path.exists', return_value=True)
    def test_dont_fetch_if_local_repo_exists(self, path_mock, git_mock):
        repositories.refreshrepo('url', 'path', self.config, branch='branch',
                                 local=True)
        expected_git_log = [mock.call.bake().log('--pretty=format:%H %ct',
                                                 '-1', '.')]
        self.assertEqual(git_mock.bake().log.call_args_list, expected_git_log)

    def test_clone_fetch_if_local_repo_missing(self, git_mock):
        repositories.refreshrepo('url', 'path', self.config, branch='branch',
                                 local=True)
        expected_git_clone = [mock.call.clone('url', 'path')]
        expected_git_fetch = [mock.call.fetch('origin')]
        expected_git_checkout = [mock.call.bake().checkout('-f', 'branch')]
        expected_git_reset = [mock.call.bake().reset('--hard',
                                                     'origin/branch')]
        expected_git_log = [mock.call.bake().log('--pretty=format:%H %ct',
                                                 '-1', '.')]

        self.assertEqual(git_mock.clone.call_args_list, expected_git_clone)
        self.assertEqual(git_mock.bake().fetch.call_args_list,
                         expected_git_fetch)
        self.assertEqual(git_mock.bake().checkout.call_args_list,
                         expected_git_checkout)
        self.assertEqual(git_mock.bake().reset.call_args_list,
                         expected_git_reset)
        self.assertEqual(git_mock.bake().log.call_args_list, expected_git_log)

    def test_clone_no_fallback(self, git_mock):
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'fallback_to_master', '0')
        self.config = ConfigOptions(config)
        git_mock.bake().branch.side_effect = _aux_git_branch
        git_mock.bake().tag.side_effect = _aux_git_tag
        git_mock.bake().checkout.side_effect = _aux_git_checkout
        self.assertRaises(sh.ErrorReturnCode_1, repositories.refreshrepo,
                          'url', 'path', self.config, branch='branch')
        expected_git_clone = [mock.call.clone('url', 'path')]
        expected_git_fetch = [mock.call.fetch('origin')]
        expected_git_checkout = [mock.call.bake().checkout('-f', 'branch')]

        self.assertEqual(git_mock.clone.call_args_list, expected_git_clone)
        self.assertEqual(git_mock.bake().fetch.call_args_list,
                         expected_git_fetch)
        self.assertEqual(git_mock.bake().checkout.call_args_list,
                         expected_git_checkout)

    def test_clone_no_fallback_default(self, git_mock):
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'fallback_to_master', '1')
        self.config = ConfigOptions(config)
        git_mock.bake().branch.side_effect = _aux_git_branch
        git_mock.bake().tag.side_effect = _aux_git_tag
        git_mock.bake().checkout.side_effect = _aux_git_checkout
        self.assertRaises(sh.ErrorReturnCode_1, repositories.refreshrepo,
                          'url', 'path', self.config, branch='rpm-master')
        expected_git_clone = [mock.call.clone('url', 'path')]
        expected_git_fetch = [mock.call.fetch('origin')]
        expected_git_checkout = [mock.call.bake().checkout('-f',
                                                           'rpm-master')]

        self.assertEqual(git_mock.clone.call_args_list, expected_git_clone)
        self.assertEqual(git_mock.bake().fetch.call_args_list,
                         expected_git_fetch)
        self.assertEqual(git_mock.bake().checkout.call_args_list,
                         expected_git_checkout)

    def test_clone_no_fallback_var(self, git_mock):
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'fallback_to_master', '1')
        config.set('DEFAULT', 'nonfallback_branches', '^foo-')
        self.config = ConfigOptions(config)
        git_mock.bake().branch.side_effect = _aux_git_branch
        git_mock.bake().tag.side_effect = _aux_git_tag
        git_mock.bake().checkout.side_effect = _aux_git_checkout
        self.assertRaises(sh.ErrorReturnCode_1, repositories.refreshrepo,
                          'url', 'path', self.config, branch='foo-bar')
        expected_git_clone = [mock.call.clone('url', 'path')]
        expected_git_fetch = [mock.call.fetch('origin')]
        expected_git_checkout = [mock.call.bake().checkout('-f', 'foo-bar')]

        self.assertEqual(git_mock.clone.call_args_list, expected_git_clone)
        self.assertEqual(git_mock.bake().fetch.call_args_list,
                         expected_git_fetch)
        self.assertEqual(git_mock.bake().checkout.call_args_list,
                         expected_git_checkout)

    def test_clone_fallback_var(self, git_mock):
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'fallback_to_master', '1')
        config.set('DEFAULT', 'nonfallback_branches', '^foo-')
        self.config = ConfigOptions(config)
        git_mock.bake().branch.side_effect = _aux_git_branch
        git_mock.bake().tag.side_effect = _aux_git_tag
        git_mock.bake().checkout.side_effect = _aux_git_checkout
        git_mock.bake().log.return_value = None
        result = repositories.refreshrepo('url', 'path', self.config,
                                          branch='zed-rdo')
        self.assertEqual(result, ['rpm-master', 'None'])
        expected_git_clone = [mock.call.clone('url', 'path')]
        expected_git_fetch = [mock.call.fetch('origin')]
        expected_git_checkout = [mock.call.bake().checkout('-f', 'zed-rdo'),
                                 mock.call.bake().checkout('rpm-master')]
        expected_git_reset = [mock.call.bake().reset('--hard',
                                                     'origin/rpm-master')]
        expected_git_log = [mock.call.bake().log('--pretty=format:%H %ct',
                                                 '-1', '.')]

        self.assertEqual(git_mock.clone.call_args_list, expected_git_clone)
        self.assertEqual(git_mock.bake().fetch.call_args_list,
                         expected_git_fetch)
        self.assertEqual(git_mock.bake().checkout.call_args_list,
                         expected_git_checkout)
        self.assertEqual(git_mock.bake().reset.call_args_list,
                         expected_git_reset)
        self.assertEqual(git_mock.bake().log.call_args_list, expected_git_log)

    def test_clone_fallback_eol(self, git_mock):
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'source', 'stable/eoled')
        config.set('DEFAULT', 'fallback_to_master', '1')
        config.set('DEFAULT', 'nonfallback_branches', '^foo-')
        self.config = ConfigOptions(config)
        git_mock.bake().branch.side_effect = _aux_git_branch
        git_mock.bake().tag.side_effect = _aux_git_tag
        git_mock.bake().checkout.side_effect = _aux_git_checkout
        git_mock.bake().log.return_value = None
        result = repositories.refreshrepo('url', 'path', self.config,
                                          branch='stable/eoled')
        self.assertEqual(result, ['eoled-eol', 'None'])
        expected_git_clone = [mock.call.clone('url', 'path')]
        expected_git_fetch = [mock.call.fetch('origin')]
        expected_git_checkout = [mock.call.bake().checkout('-f',
                                                           'stable/eoled'),
                                 mock.call.bake().checkout('eoled-eol')]
        expected_git_tag = [mock.call.tag('-l', 'eoled-eol')]
        expected_git_reset = [mock.call.bake().reset('--hard',
                                                     'origin/eoled-eol')]
        expected_git_log = [mock.call.bake().log('--pretty=format:%H %ct',
                                                 '-1', '.')]

        self.assertEqual(git_mock.clone.call_args_list, expected_git_clone)
        self.assertEqual(git_mock.bake().fetch.call_args_list,
                         expected_git_fetch)
        self.assertEqual(git_mock.bake().checkout.call_args_list,
                         expected_git_checkout)
        self.assertEqual(git_mock.bake().tag.call_args_list, expected_git_tag)
        self.assertEqual(git_mock.bake().reset.call_args_list,
                         expected_git_reset)
        self.assertEqual(git_mock.bake().log.call_args_list, expected_git_log)

    def test_clone_fallback_branchless(self, git_mock):
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'source', 'stable/branchless')
        config.set('DEFAULT', 'fallback_to_master', '1')
        config.set('DEFAULT', 'nonfallback_branches', '^foo-')
        self.config = ConfigOptions(config)
        git_mock.bake().branch.side_effect = _aux_git_branch
        git_mock.bake().tag.side_effect = _aux_git_tag
        git_mock.bake().checkout.side_effect = _aux_git_checkout
        git_mock.bake().log.return_value = None
        result = repositories.refreshrepo('url', 'path', self.config,
                                          branch='stable/branchless')
        self.assertEqual(result, ['master', 'None'])
        expected_git_clone = [mock.call.clone('url', 'path')]
        expected_git_fetch = [mock.call.fetch('origin')]
        expected_git_checkout = [mock.call.bake()
                                 .checkout('-f', 'stable/branchless'),
                                 mock.call.bake().checkout('master')]
        expected_git_tag = [mock.call.tag('-l', 'branchless-eol')]
        expected_git_branch = [mock.call.branch('--list', 'master')]
        expected_git_reset = [mock.call.bake().reset('--hard',
                                                     'origin/master')]
        expected_git_log = [mock.call.bake().log('--pretty=format:%H %ct',
                                                 '-1', '.')]

        self.assertEqual(git_mock.clone.call_args_list, expected_git_clone)
        self.assertEqual(git_mock.bake().fetch.call_args_list,
                         expected_git_fetch)
        self.assertEqual(git_mock.bake().checkout.call_args_list,
                         expected_git_checkout)
        self.assertEqual(git_mock.bake().tag.call_args_list, expected_git_tag)
        self.assertEqual(git_mock.bake().branch.call_args_list,
                         expected_git_branch)
        self.assertEqual(git_mock.bake().reset.call_args_list,
                         expected_git_reset)
        self.assertEqual(git_mock.bake().log.call_args_list, expected_git_log)

    def test_clone_fallback_main(self, git_mock):
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'source', 'stable/branchless')
        config.set('DEFAULT', 'fallback_to_master', '1')
        config.set('DEFAULT', 'nonfallback_branches', '^foo-')
        self.config = ConfigOptions(config)
        git_mock.bake().branch.side_effect = _aux_git_branch_main
        git_mock.bake().tag.side_effect = _aux_git_tag
        git_mock.bake().checkout.side_effect = _aux_git_checkout
        git_mock.bake().log.return_value = None
        result = repositories.refreshrepo('url', 'path', self.config,
                                          branch='stable/branchless')
        self.assertEqual(result, ['main', 'None'])
        expected_git_clone = [mock.call.clone('url', 'path')]
        expected_git_fetch = [mock.call.fetch('origin')]
        expected_git_checkout = [mock.call.bake()
                                 .checkout('-f', 'stable/branchless'),
                                 mock.call.bake().checkout('main')]
        expected_git_tag = [mock.call.tag('-l', 'branchless-eol')]
        expected_git_branch = [mock.call.branch('--list', 'master'),
                               mock.call.branch('--list', 'main')]
        expected_git_reset = [mock.call.bake().reset('--hard',
                                                     'origin/main')]
        expected_git_log = [mock.call.bake().log('--pretty=format:%H %ct',
                                                 '-1', '.')]

        self.assertEqual(git_mock.clone.call_args_list, expected_git_clone)
        self.assertEqual(git_mock.bake().fetch.call_args_list,
                         expected_git_fetch)
        self.assertEqual(git_mock.bake().checkout.call_args_list,
                         expected_git_checkout)
        self.assertEqual(git_mock.bake().tag.call_args_list, expected_git_tag)
        self.assertEqual(git_mock.bake().branch.call_args_list,
                         expected_git_branch)
        self.assertEqual(git_mock.bake().reset.call_args_list,
                         expected_git_reset)
        self.assertEqual(git_mock.bake().log.call_args_list, expected_git_log)

    def test_clone_no_fallback_nosource(self, git_mock):
        config = configparser.RawConfigParser()
        config.read("projects.ini")
        config.set('DEFAULT', 'source', 'stable/release')
        config.set('DEFAULT', 'fallback_to_master', '1')
        self.config = ConfigOptions(config)
        git_mock.bake().branch.side_effect = _aux_git_branch
        git_mock.bake().tag.side_effect = _aux_git_tag
        git_mock.bake().checkout.side_effect = _aux_git_checkout
        git_mock.bake().log.return_value = None
        self.assertRaises(sh.ErrorReturnCode_1, repositories.refreshrepo,
                          'url', 'path', self.config, branch='1.0.0')
        expected_git_clone = [mock.call.clone('url', 'path')]
        expected_git_fetch = [mock.call.fetch('origin')]
        expected_git_checkout = [mock.call.bake().checkout('-f', '1.0.0')]

        self.assertEqual(git_mock.clone.call_args_list, expected_git_clone)
        self.assertEqual(git_mock.bake().fetch.call_args_list,
                         expected_git_fetch)
        self.assertEqual(git_mock.bake().checkout.call_args_list,
                         expected_git_checkout)
