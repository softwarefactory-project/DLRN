# Copyright (c) 2019 Red Hat
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

import logging
import subprocess

from dlrn.drivers.buildcontainer import BuildContainerDriver

logger = logging.getLogger("dlrn-build-buildah")


def pread(argv):
    logger.debug("Running %s", argv)
    return subprocess.Popen(
        argv, stdout=subprocess.PIPE).stdout.read().strip().decode('utf-8')


def execute(argv):
    logger.debug("Running %s", argv)
    if subprocess.Popen(argv).wait():
        raise RuntimeError("Couldn't run %s" % " ".join(argv))


class BuildahDriver(BuildContainerDriver):
    DRIVER_CONFIG = {
        'buildah_driver': {
        }
    }

    def build(self, container, mnt):
        print("TODO!")

    def build_container(self, commit):
        tagname = "{project_name}:{commit_hash}-{distro_hash}".format(
            **commit.__dict__)
        logger.info("Building %s", tagname)
        container = pread(["buildah", "from", "centos:latest"]).strip()
        try:
            try:
                mnt = pread(["buildah", "mount", container]).strip()
                self.build(container, mnt)
                execute(["buildah", "commit", container, tagname])
            finally:
                execute(["buildah", "umount", container])
        finally:
            execute(["buildah", "delete", container])


if __name__ == "__main__":
    import dlrn.config
    import dlrn.db
    import six.moves
    import sys

    dlrn.config.setup_logging(True)
    cp = six.moves.configparser.RawConfigParser()
    cp.read("projects.ini")
    config_options = dlrn.config.ConfigOptions(cp)

    session = dlrn.db.getSession(config_options.database_connection)
    commit = session.query(dlrn.db.Commit).filter(
        dlrn.db.Commit.id == int(sys.argv[1])).one()
    BuildahDriver().build_container(commit)
