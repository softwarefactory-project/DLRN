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

from dlrn.drivers.buildrpm import BuildRPMDriver

import logging
import os
import sh

RPM_AVAILABLE = False
try:
    import rpm
    RPM_AVAILABLE = True
except ImportError:
    pass


logging.basicConfig(level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("dlrn-build-brew")
logger.setLevel(logging.INFO)


class BrewBuildDriver(BuildRPMDriver):
    def __init__(self, *args, **kwargs):
        super(BrewBuildDriver, self).__init__(*args, **kwargs)

    def build_package(self, **kwargs):
        """Valid parameters:

        :param output_directory: directory where the SRPM is located,
                                 and the built packages will be.
        :param package_name: name of a package to build
        """
        output_dir = kwargs.get('output_directory')
        # find .src.rpm
        src_rpm = None
        srpms = ['%s/%s' % (output_dir, rpm) for rpm in os.listdir(output_dir)
                 if rpm.endswith(".src.rpm")]
        if len(srpms) == 0:
            raise Exception("Couldn't find .src.rpm to build.")
        elif len(srpms) == 1:
            src_rpm = srpms[0]
        else:
            # Pick the srpms with highest NVR
            srpms = sorted(srpms, key=cmp_to_key(_rpms_vercmp))
            src_rpm = srpms[-1]

        # find distgit and branch to import into
        package_name = kwargs.get('package_name')
        if not package_name:
            raise Exception("BrewBuildDriver requires package_name")
        # XXX: this should be easily accessible helper function
        distgit_dir = os.path.join(
            self.config_options.datadir,
            package_name + "_distro")
        distgit_branch = self.config_options.downstream_distro_branch

        git = sh.git.bake(_cwd=distgit_dir, _tty_out=False, _timeout=3600)
        rhpkg = sh.rhpkgdebug.bake(_cwd=distgit_dir, _tty_out=False,
                                   _timeout=3600)

        git('checkout', distgit_branch)
        rhpkg('import', '--skip-diff', src_rpm)
        rhpkg('push')
        rhpkg('build')


# FIXME(hguemar): should be moved elsewhere
def _rpms_vercmp(rpm1, rpm2):
    """Compare two RPMS (including Source RPMS)

    :param rpm1: path to an actual RPM
    :param rpm2: path to an actual RPM
    :return: 0 if same NVR, 1 if rpm1 > rpm2, -1 if rpm1 < rpm2
    """
    if not RPM_AVAILABLE:
        raise Exception("No rpm module available")
    # FIXME(hguemar): since we feed it with a list of files from disk
    # assumes that files do exist.
    f1 = open(rpm1, 'r')
    f2 = open(rpm2, 'r')
    ts = rpm.ts()
    hdr1 = ts.hdrFromFdno(f1)
    hdr2 = ts.hdrFromFdno(f2)
    return rpm.versionCompare(hdr1, hdr2)
