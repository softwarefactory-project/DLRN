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

import base64
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
            'fetch_container': {'type': 'boolean', 'default': False},
            'registry_upload': {'type': 'boolean', 'default': False},
            'registry_insecure': {'type': 'boolean', 'default': False},
            'registry_user': {'default': ''},
            'registry_password': {'default': ''},
            'registry_namespace': {'default': ''},
            'registry_server': {'default': ''},
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

    def _generate_authfile(self, path, server, user, password):
        plain_creds = '%s:%s' % (user, password)
        hashed_creds = base64.b64encode(plain_creds.encode()).decode()
        with open(path, 'w') as fp:
            fp.write('{\n\t"auths": {\n')
            fp.write('\t\t"%s": {\n' % server)
            fp.write('\t\t\t"auth": "%s"\n' % hashed_creds)
            fp.write('\t\t}\n\t}\n}')

    def build_with_buildah(self, package_name, commit, tag, output_dir):
        run_cmd = []
        run_cmd.extend(
            [self.exe_name,
             'build-using-dockerfile',
             '-t', '%s:%s' % (package_name, tag),
             '-f', 'Dockerfile',
             '.'])
        with io.open("%s/build.log" % output_dir, 'a',
                     encoding='utf-8', errors='replace') as self.fp:
            try:
                sh.env(run_cmd, _err=self._process_dockerfile_output,
                       _out=self._process_dockerfile_output,
                       _cwd=commit.distgit_dir)
            except Exception as e:
                raise e

        if self.config_options.fetch_container:
            run_cmd = []
            run_cmd.extend(
                ['podman',
                 'image', 'save',
                 '%s:%s' % (package_name, tag),
                 '-o',
                 '%s/%s_%s.tar' % (output_dir, package_name, tag)])
            with io.open("%s/fetch.log" % output_dir, 'a',
                         encoding='utf-8', errors='replace') as self.fp:
                try:
                    sh.env(run_cmd, _err=self._process_dockerfile_output,
                           _out=self._process_dockerfile_output,
                           _cwd=output_dir)
                except Exception as e:
                    raise e
        return None

    def build_with_docker(self, package_name, commit, tag, output_dir,
                          authfile_path):
        pass

    def upload_with_podman(self, package_name, commit, tag, output_dir,
                           authfile_path):
        run_cmd = []
        run_cmd.extend(
            ['podman', 'login',
             '--authfile=%s' % authfile_path,
             '--tls-verify=%s' % (not self.config_options.registry_insecure),
             self.config_options.registry_server])
        with io.open("%s/registry_login.log" % output_dir, 'a',
                     encoding='utf-8', errors='replace') as self.fp:
            try:
                sh.env(run_cmd, _err=self._process_dockerfile_output,
                       _out=self._process_dockerfile_output,
                       _cwd=output_dir)
            except Exception as e:
                raise e

        run_cmd = []
        run_cmd.extend(
            ['podman', 'tag',
             '%s:%s' % (package_name, tag),
             '%s/%s/%s:%s' % (self.config_options.registry_server,
                              self.config_options.registry_namespace,
                              package_name,
                              tag)])
        run2_cmd = []
        run2_cmd.extend(
            ['podman', 'push',
             '--tls-verify=%s' % (not self.config_options.registry_insecure),
             '%s/%s/%s:%s' % (self.config_options.registry_server,
                              self.config_options.registry_namespace,
                              package_name,
                              tag)])
        with io.open("%s/registry_upload.log" % output_dir, 'a',
                     encoding='utf-8', errors='replace') as self.fp:
            try:
                sh.env(run_cmd, _err=self._process_dockerfile_output,
                       _out=self._process_dockerfile_output,
                       _cwd=output_dir)
                sh.env(run2_cmd, _err=self._process_dockerfile_output,
                       _out=self._process_dockerfile_output,
                       _cwd=output_dir)
            except Exception as e:
                raise e
        return None

    def upload_with_docker(self, package_name, commit, tag, output_dir):
        return None

    def build_container(self, **kwargs):
        """Valid parameters:

        :param output_directory: directory where the SRPM is located,
                                 and the built packages will be.
        :param package_name: name of a package to build
        """
        output_dir = kwargs.get('output_directory')
        package_name = kwargs.get('package_name')
        commit = kwargs.get('commit')
        tag = os.path.basename(commit.getshardedcommitdir())

        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)

        try:
            if self.exe_name == 'buildah':
                build_method = self.build_with_buildah
            else:
                build_method = None  # FIXME
            build_method(package_name, commit, tag, output_dir)
        except Exception as e:
            raise e

        try:
            if self.config_options.registry_upload:
                datadir = os.path.realpath(self.config_options.datadir)
                authfile_path = os.path.join(datadir, 'auth.json')
                self._generate_authfile(authfile_path,
                                        self.config_options.registry_server,
                                        self.config_options.registry_user,
                                        self.config_options.registry_password)

                if self.exe_name == 'buildah':
                    upload_method = self.upload_with_podman
                else:
                    upload_method = self.upload_with_docker
                upload_method(package_name, commit, tag, output_dir,
                              authfile_path)
        except Exception as e:
            raise e

        return ['%s:%s' % (package_name, commit.commit_hash)]
