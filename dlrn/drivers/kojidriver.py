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

# BuildRPMDriver derived classes expose the following methods:
#
# build_package(). This method will perform the actual package build using
#                  the driver-specific approach.

from dlrn.drivers.buildrpm import BuildRPMDriver
import dlrn.shell

import io
import logging
import os
import re
import sh

logging.basicConfig(level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("dlrn-build-koji")
logger.setLevel(logging.INFO)

# FIXME(jpena): needs to be configurable, and driver-independent
mock_base_packages = "basesystem rpm-build python2-devel gcc make "\
                     "python-sqlalchemy python-webob ghostscript graphviz "\
                     "python-sphinx python-eventlet python-six python-pbr "\
                     "openstack-macros git yum-plugin-priorities rubygems"


class KojiBuildDriver(BuildRPMDriver):
    def __init__(self, *args, **kwargs):
        super(KojiBuildDriver, self).__init__(*args, **kwargs)
        self.exe_name = self.config_options.koji_exe

    # We are using this method to "tee" koji output to a log file and stdout
    def _process_koji_output(self, line):
        if dlrn.shell.verbose_build:
            logger.info(line[:-1])
        self.koji_fp.write(line)

    def write_mock_config(self, filename):
        """Retrieve mock config from Koji instance

        :param filename: output filename to write mock config
        """
        target = self.config_options.koji_build_target
        arch = self.config_options.koji_arch
        run_cmd = [self.exe_name]
        run_cmd.extend(['mock-config',
                        '--arch', arch, '--target', target, '-o', filename])
        # FIXME(hguemar): add proper exception management
        sh.env(run_cmd,
               _env={'PATH': '/usr/bin/'})
        lines = []
        with open(filename, 'r') as fp:
            for line in fp.readlines():
                if line.startswith("config_opts['chroot_setup_cmd']"):
                    lines.append("config_opts['chroot_setup_cmd'] = "
                                 "'install %s'\n" % mock_base_packages)
                else:
                    lines.append(line)
        with open(filename, 'w') as fp:
            fp.write(''.join(lines))

    def build_package(self, **kwargs):
        """Valid parameters:

        :param output_directory: directory where the SRPM is located,
                                 and the built packages will be.
        """
        output_dir = kwargs.get('output_directory')
        krb_principal = self.config_options.koji_krb_principal
        keytab_file = self.config_options.koji_krb_keytab
        scratch = self.config_options.koji_scratch_build
        target = self.config_options.koji_build_target

        # Find src.rpm
        for rpm in os.listdir(output_dir):
            if rpm.endswith(".src.rpm"):
                src_rpm = '%s/%s' % (output_dir, rpm)
        try:
            # Build package using koji/brew
            run_cmd = [self.exe_name]
            if krb_principal:
                run_cmd.extend(['--principal', krb_principal,
                                '--keytab', keytab_file])
            run_cmd.extend(['build', '--wait',
                            target, src_rpm])

            build_exception = None
            with io.open("%s/kojibuild.log" % output_dir, 'a',
                         encoding='utf-8', errors='replace') as self.koji_fp:
                try:
                    sh.env(run_cmd, _err=self._process_koji_output,
                           _out=self._process_koji_output,
                           _cwd=output_dir, scratch=scratch,
                           _env={'PATH': '/usr/bin/'})
                except Exception as e:
                    build_exception = e

            # Find task id to download logs
            with open("%s/kojibuild.log" % output_dir, 'r') as fp:
                log_content = fp.readlines()
            task_id = None
            for line in log_content:
                m = re.search("^Created task: (\d+)$", line)
                if m:
                    logger.info("Created task id %s" % m.group(1))
                    task_id = m.group(1)
                    break

            if not task_id:
                raise Exception('Failed to find task id for the koji build')

            # Download build artifacts and logs
            run_cmd = []
            run_cmd.extend(
                [self.exe_name,
                 'download-task', '--logs',
                 task_id])

            with io.open("%s/kojidownload.log" % output_dir, 'a',
                         encoding='utf-8', errors='replace') as self.koji_fp:
                try:
                    sh.env(run_cmd, _err=self._process_koji_output,
                           _out=self._process_koji_output,
                           _cwd=output_dir, _env={'PATH': '/usr/bin/'})
                except Exception as e:
                    raise e

            # All went fine, create the $OUTPUT_DIRECTORY/installed file
            open('%s/installed' % output_dir, 'a').close()
        finally:
            # Finally run restorecon
            try:
                sh.restorecon('-Rv', output_dir)
            except Exception as e:
                logger.info('restorecon did not run correctly, %s' % e)

            # We only want to raise the build exception at the very end, after
            # downloading all relevant artifacts
            if build_exception:
                raise build_exception
