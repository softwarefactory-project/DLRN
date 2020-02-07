# Copyright (c) 2020 Red Hat
#
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

from dlrn.drivers.buildcontainer import BuildContainerDriver
import dlrn.shell

import io
import logging
import os
import sh
import shutil

logger = logging.getLogger("dlrn-build-dockerfile")


class DockerfileDriver(BuildContainerDriver):
    DRIVER_CONFIG = {
        'dockerfile_driver': {
            'dockerfile_exe': {'name': 'exe', 'default': 'buildah'},
            'registry_upload': {'type': 'boolean', 'default': False},
            'registry_user': {'default': ''},
            'registry_password': {'default': ''},
        }
    }

    def __init__(self, *args, **kwargs):
        super(DockerfileDriver, self).__init__(*args, **kwargs)
        self.exe_name = self.config_options.dockerfile_exe

    # We are using this method to "tee" koji output to a log file and stdout
    def _process_dockerfile_output(self, line):
        if dlrn.shell.verbose_build:
            logger.info(line[:-1])
        self.fp.write(line)

    def build_with_buildah(self, package_name, commit, output_dir):
        run_cmd = []
        run_cmd.extend(
            [self.exe_name,
             'build-using-dockerfile',
             '-t', '%s:%s' % (package_name, commit.commit_hash),
             '-f', 'Dockerfile',
             '.'])
        with io.open("%s/build.log" % output_dir, 'a',
                     encoding='utf-8', errors='replace') as self.fp:
            try:
                sh.env(run_cmd, _err=self._process_dockerfile_output,
                       _out=self._process_dockerfile_output,
                       _cwd=commit.distgit_dir)
            except Exception as e:
                build_exception = e
                return build_exception

        # FIXME (jpena): make this whole download part optional
        run_cmd = []
        run_cmd.extend(
            ['podman',
             'image', 'save',
             '%s:%s' % (package_name, commit.commit_hash),
             '-o',
             '%s/%s_%s.tar' % (output_dir, package_name, commit.commit_hash)])
        with io.open("%s/export.log" % output_dir, 'a',
                     encoding='utf-8', errors='replace') as self.fp:
            try:
                sh.env(run_cmd, _err=self._process_dockerfile_output,
                       _out=self._process_dockerfile_output,
                       _cwd=output_dir)
            except Exception as e:
                build_exception = e
                return build_exception
        return None

    def build_with_docker(self, package_name, commit, output_dir):
        pass

    def build_container(self, **kwargs):
        """Valid parameters:

        :param output_directory: directory where the SRPM is located,
                                 and the built packages will be.
        :param package_name: name of a package to build
        """
        output_dir = kwargs.get('output_directory')
        package_name = kwargs.get('package_name')
        commit = kwargs.get('commit')

        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)

        try:
            if self.exe_name == 'buildah':
                build_method = self.build_with_buildah
            else:
                build_method = None  # FIXME

            build_exception = build_method(package_name, commit, output_dir)

            # FIXME (jpena): Add the registry upload here, if applicable
        finally:
            # We only want to raise the build exception at the very end, after
            # downloading all relevant artifacts
            if build_exception:
                raise build_exception
        return ['%s:%s' % (package_name, commit.commit_hash)]
