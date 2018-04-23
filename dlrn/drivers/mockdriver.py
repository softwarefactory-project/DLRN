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

import logging
import os
import re
import sh

logging.basicConfig(level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("dlrn-build-mock")
logger.setLevel(logging.INFO)


class MockBuildDriver(BuildRPMDriver):
    # We are using this method to "tee" mock output to mock.log and stdout
    def _process_mock_output(self, line):
        if dlrn.shell.verbose_mock:
            logger.info(line[:-1])
        self.mock_fp.write(line)

    def __init__(self, *args, **kwargs):
        super(MockBuildDriver, self).__init__(*args, **kwargs)

    def build_package(self, **kwargs):
        """Valid parameters:

        :param output_directory: directory where the SRPM is located,
                                 and the built packages will be.
        """
        output_dir = kwargs.get('output_directory')
        datadir = os.path.realpath(self.config_options.datadir)
        additional_mock_opts = os.environ.get('ADDITIONAL_MOCK_OPTIONS')
        mock_config = os.environ.get('MOCK_CONFIG')

        # Find src.rpm
        for rpm in os.listdir(output_dir):
            if rpm.endswith(".src.rpm"):
                src_rpm = '%s/%s' % (output_dir, rpm)
        try:
            # And build package
            with open("%s/mock.log" % output_dir, 'a') as self.mock_fp:
                try:
                    if additional_mock_opts:
                        sh.mock('-v', '-r', '%s/%s' % (datadir, mock_config),
                                '--resultdir', output_dir,
                                additional_mock_opts,
                                '--postinstall', '--rebuild',
                                src_rpm, _err=self._process_mock_output,
                                _out=self._process_mock_output)
                    else:
                        sh.mock('-v', '-r', '%s/%s' % (datadir, mock_config),
                                '--resultdir', output_dir,
                                '--postinstall', '--rebuild',
                                src_rpm, _err=self._process_mock_output,
                                _out=self._process_mock_output)
                except Exception as e:
                    raise e

            # Check for warning about built packages failing to install
            with open("%s/mock.log" % output_dir, 'r') as fp:
                mock_content = fp.readlines()

            warn_match = re.compile(
                '\W*WARNING: Failed install built packages.*')
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
