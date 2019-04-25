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
import os
import shutil
import subprocess

from dlrn.config import getConfigOptions
from dlrn.db import getSession, Commit
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


def getRpmRepos(commit):
    session = getSession(getConfigOptions().database_connection)
    try:
        return session.query(Commit).filter(
            Commit.project_name == commit.project_name,
            Commit.type == "rpm",
            Commit.commit_branch == commit.commit_branch,
            Commit.dt_distro == commit.dt_distro,
            Commit.commit_hash == commit.commit_hash,
            Commit.distro_hash == commit.distro_hash,
        ).one().artifacts
    except Exception:
        logger.exception("Couldn't get previously built rpms")
        raise


class BuildahDriver(BuildContainerDriver):
    DRIVER_CONFIG = {
        'buildah_driver': {
        }
    }

    def build(self, container, mnt, rpms):
        to_install = set()
        datadir = getConfigOptions().datadir
        for rpm in rpms:
            if rpm.endswith(".src.rpm"):
                continue
            to_install.add("/%s" % os.path.basename(rpm))
            shutil.copy(os.path.join(datadir, rpm), mnt)

        execute(["buildah", "run", container, "yum", "install", "-y"] +
                list(to_install))

        for rpm in to_install:
            os.unlink(os.path.join(mnt, rpm[1:]))

    def build_container(self, commit):
        tagname = "{project_name}:{commit_hash}-{distro_hash}".format(
            **commit.__dict__)
        logger.info("Building %s", tagname)
        rpms = getRpmRepos(commit).split(',')
        container = pread(["buildah", "from", "centos:latest"]).strip()
        try:
            try:
                mnt = pread(["buildah", "mount", container]).strip()
                self.build(container, mnt, rpms)
                execute(["buildah", "commit", container, tagname])
            finally:
                execute(["buildah", "umount", container])
        finally:
            execute(["buildah", "delete", container])
        return [tagname]
