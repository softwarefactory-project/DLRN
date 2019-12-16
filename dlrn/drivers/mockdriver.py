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

logger = logging.getLogger("dlrn-build-mock")


class MockBuildDriver(BuildRPMDriver):
    DRIVER_CONFIG = {
        'mockbuild_driver': {
            'install_after_build': {'type': 'boolean', 'default': True},
        },
    }

    # We are using this method to "tee" mock output to mock.log and stdout
    def _process_mock_output(self, line):
        if dlrn.shell.verbose_build:
            logger.info(line[:-1])
        self.mock_fp.write(line)

    def __init__(self, *args, **kwargs):
        super(MockBuildDriver, self).__init__(*args, **kwargs)

    def build_package(self, **kwargs):
        """Valid parameters:

        :param output_directory: directory where the SRPM is located,
                                 and the built packages will be.
        :param additional_mock_opts: string with additional options to
                                     be passed to mock.
        """
        output_dir = kwargs.get('output_directory')
        additional_mock_opts = kwargs.get('additional_mock_opts')
        datadir = os.path.realpath(self.config_options.datadir)
        mock_config = os.environ.get('MOCK_CONFIG')
        install_after_build = self.config_options.install_after_build

        # Find src.rpm
        for rpm in os.listdir(output_dir):
            if rpm.endswith(".src.rpm"):
                src_rpm = '%s/%s' % (output_dir, rpm)
        try:
            # And build package
            with io.open("%s/mock.log" % output_dir, 'a',
                         encoding='utf-8', errors='replace') as self.mock_fp:
                try:
                    mock_opts = ['-v', '-r', '%s/%s' % (datadir, mock_config),
                                 '--resultdir', output_dir]
                    if additional_mock_opts:
                        mock_opts += [additional_mock_opts]
                    mock_opts += ['--rebuild', src_rpm]
                    sh.env('/usr/bin/mock', *mock_opts,
                           postinstall=install_after_build,
                           _err=self._process_mock_output,
                           _out=self._process_mock_output)
                except Exception as e:
                    raise e

            if install_after_build:
                # Check for warning about built packages failing to install
                with open("%s/mock.log" % output_dir, 'r') as fp:
                    mock_content = fp.readlines()
                warn_match = re.compile(
                    r'\W*WARNING: Failed install built packages.*')
                for line in mock_content:
                    m = warn_match.match(line)
                    if m is not None:
                        raise Exception('Failed to install built packages')

            # All went fine, create the $OUTPUT_DIRECTORY/installed file
            open('%s/installed' % output_dir, 'a').close()

        finally:
            with open("%s/mock.log" % output_dir, 'r') as fp:
                mock_content = fp.readlines()

            # Append mock output to rpmbuild.log
            with open('%s/rpmbuild.log' % output_dir, 'a') as fp:
                for line in mock_content:
                    fp.write(line)

            # Finally run restorecon
            try:
                sh.restorecon('-Rv', output_dir)
            except Exception as e:
                logger.info('restorecon did not run correctly, %s' % e)
