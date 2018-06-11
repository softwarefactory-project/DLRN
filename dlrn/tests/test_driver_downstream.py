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
import shutil
import tempfile

from dlrn.config import ConfigOptions
from dlrn.drivers.downstream import DownstreamInfoDriver
from dlrn.shell import default_options
from dlrn.tests import base
from six.moves import configparser


def _mocked_versions(*args, **kwargs):
    fn = './dlrn/tests/samples/versions.csv'
    return open(fn, 'rb')


@mock.patch('dlrn.drivers.downstream.urlopen', side_effect=_mocked_versions)
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

    def test_versions_parse(self, uo_mock):
        driver = DownstreamInfoDriver(cfg_options=self.config)
        versions = driver.getversions()
        nv = versions['openstack-nova']
        assert nv[1] == 'ef6b4f43f467dfad2fd0fe99d9dec3fc93a9ffed', nv[1]
        assert nv[3] == '8fce438abdd12cba33bd9fa4f7d16c098e10094f', nv[3]

    def test_getinfo(self, uo_mock):
        driver = DownstreamInfoDriver(cfg_options=self.config)
        package = {
            'name': 'openstack-nova',
            'project': 'nova',
            'conf': 'rpmfactory-core',
            'upstream': 'git://git.openstack.org/openstack/nova',
            'patches': 'http://review.rdoproject.org/r/p/openstack/nova.git',
            'distgit': 'https://github.com/rdo-packages/nova-distgit.git',
            'master-distgit':
                'https://github.com/rdo-packages/nova-distgit.git',
            'name': 'openstack-nova',
            'buildsys-tags': [
                'cloud7-openstack-pike-release: openstack-nova-16.1.4-1.el7',
                'cloud7-openstack-pike-testing: openstack-nova-16.1.4-1.el7',
                'cloud7-openstack-queens-release: openstack-nova-17.0.5-1.el7',
                'cloud7-openstack-queens-testing: openstack-nova-17.0.5-1.el7',
            ]
        }
        pkginfo = driver.getinfo(
            package=package,
            project='test',
            dev_mode=True)
        pi = pkginfo[0]
        assert pi.commit_hash == '8fce438abdd12cba33bd9fa4f7d16c098e10094f', \
            pi.commit_hash
