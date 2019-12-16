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
import shutil

logger = logging.getLogger("dlrn-build-copr")


class CoprBuildDriver(BuildRPMDriver):
    DRIVER_CONFIG = {
        'coprbuild_driver': {
            'coprid': {},
        }
    }

    def __init__(self, *args, **kwargs):
        super(CoprBuildDriver, self).__init__(*args, **kwargs)
        self.exe_name = 'copr'

    # We are using this method to "tee" copr output to a log file and stdout
    def _process_copr_output(self, line):
        if dlrn.shell.verbose_build:
            logger.info(line[:-1])
        self.copr_fp.write(line)

    def build_package(self, **kwargs):
        """Valid parameters:

        :param output_directory: directory where the SRPM is located,
                                 and the built packages will be.
        """
        output_dir = kwargs.get('output_directory')
        coprid = self.config_options.coprid

        # Find src.rpm
        for rpm in os.listdir(output_dir):
            if rpm.endswith(".src.rpm"):
                src_rpm = '%s/%s' % (output_dir, rpm)
        try:
            # Build package using copr
            run_cmd = []
            run_cmd.extend(
                [self.exe_name, 'build',
                 coprid, src_rpm])

            build_exception = None
            with io.open("%s/coprbuild.log" % output_dir, 'a',
                         encoding='utf-8', errors='replace') as self.copr_fp:
                try:
                    sh.env(run_cmd, _err=self._process_copr_output,
                           _out=self._process_copr_output,
                           _cwd=output_dir,
                           _env={'PATH': '/usr/bin/'})
                except Exception as e:
                    build_exception = e

            # Find task id to download logs
            with open("%s/coprbuild.log" % output_dir, 'r') as fp:
                log_content = fp.readlines()
            build_id = None
            for line in log_content:
                m = re.search(r'^Created builds: (\d+)$', line)
                if m:
                    logger.info("Created build id %s" % m.group(1))
                    build_id = m.group(1)
                    break

            if not build_id:
                raise Exception('Failed to find build id for the copr build')

            # Download build artifacts and logs
            ddir = "%s/%s" % (output_dir, build_id)
            run_cmd = []
            run_cmd.extend(
                [self.exe_name, 'download-build', '-d', ddir, build_id])

            with io.open("%s/coprdownload.log" % output_dir, 'a',
                         encoding='utf-8', errors='replace') as self.copr_fp:
                try:
                    sh.env(run_cmd, _err=self._process_copr_output,
                           _out=self._process_copr_output,
                           _cwd=output_dir, _env={'PATH': '/usr/bin/'})
                except Exception as e:
                    raise e

            # Move specific download files in output_dir
            exts_filter = ['.rpm', '.log.gz']
            # Only a directory named with the build target name
            # must be in download directory
            target_name = os.listdir(ddir)[0]
            target_dir = os.path.join(ddir, target_name)
            # Do the copy of file we care of
            for f in os.listdir(target_dir):
                if any([f.endswith(ft) for ft in exts_filter]):
                    src = os.path.join(target_dir, f)
                    dst = os.path.join(output_dir, f)
                    logger.info("Copying %s to %s" % (src, dst))
                    shutil.copy(src, dst)
            # Remove download directory
            logger.info("Removing %s" % ddir)
            shutil.rmtree(ddir)

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
