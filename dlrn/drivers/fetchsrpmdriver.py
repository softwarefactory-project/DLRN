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

from dlrn.drivers.srpm import SRPMDriver

import logging

logging.basicConfig(level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("dlrn-srpm")
logger.setLevel(logging.INFO)


def fail_req_config_missing(opt_name):
    raise Exception(
        "Missing required config option '%s' "
        "for dlrn.drivers.fetchsrpmdriver driver." % opt_name)


def fail_req_param_missing(param_name):
    raise Exception(
        "Missing required parameter '%s' "
        "for FetchSRPMDriver.prepare_srpm()" % param_name)


class FetchSRPMDriver(SRPMDriver):
    """This driver fetches .src.rpm from custom URL."""

    def __init__(self, *args, **kwargs):
        super(SRPMDriver, self).__init__(*args, **kwargs)

    def prepare_srpm(self, **kwargs):
        """Valid parameters:

        :param output_directory: directory where the SRPM is located,
                                 and the built packages will be.
        """
        srpm_base_url = getattr('srpm_base_url', self.config_options, None)
        if not srpm_base_url:
            fail_req_config_missing('srpm_base_url')
        commit = kwargs.get('commit')
        if not commit:
            fail_req_param_missing('commit')

        raise Exception("WIP: download .src.rpm from srpm_base_url")
        # TODO(jruzicka):
        # * Pass enough params to be able to construct full SRPM URL.
        #   * We have srpm_base_url and commit.project_name available here,
        #     but we need a robust way to construct full SRPM name so how do
        #     we do that? I assume we need to reuse some build_srpm.sh logic?
        #     (at least Version and Release needed)
        #   * Alternatively, we could require RPM repo instead of generic
        #     base URL (srpm_base_url would become srpm_repo) and query that
        #     repo for SRPMs. That would be slow, however.
        #     (at least Version needed)
        # * Download SRPM into output_dir.
