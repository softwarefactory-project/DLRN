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
import tempfile

from dlrn.config import ConfigOptions
from dlrn.drivers.downstream import DownstreamInfoDriver
from dlrn.shell import default_options
from dlrn.tests import base
from six.moves import configparser


def _mocked_versions(*args, **kwargs):
    fn = './dlrn/tests/samples/versions.csv'
    return open(fn, 'rb').read()


@mock.patch('sh.restorecon', create=True)
@mock.patch('sh.env', create=True)
@mock.patch('six.moves.urllib.request.urlopen', side_effect=_mocked_versions)
class TestDriverDownstream(base.TestCase):
    def setUp(self):
        super(TestDriverDownstream, self).setUp()
        config = configparser.RawConfigParser(default_options)
        config.read("projects.ini")
        self.config = ConfigOptions(config)
        self.config.versions_url = \
            'https://trunk.rdoproject.org/centos7-master/current/versions.csv'
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        super(TestDriverDownstream, self).tearDown()
        shutil.rmtree(self.temp_dir)

    def test_versions_parse(self, env_mock, rc_mock, uo_mock):
        driver = DownstreamInfoDriver(cfg_options=self.config)
        versions = driver.getversions()
        nova = [
            # XXX: hardcoded from versions.csv, could be read dynamically
            'git://git.openstack.org/openstack/nova',
            'ef6b4f43f467dfad2fd0fe99d9dec3fc93a9ffed',
            'https://github.com/rdo-packages/nova-distgit.git',
            '8fce438abdd12cba33bd9fa4f7d16c098e10094f',
            'SUCCESS',
            '1528704709',
            'openstack-nova-18.0.0-0.20180611081317.ef6b4f4.el7']
        assert versions['openstack-nova'] == nova
