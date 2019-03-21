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
import re
import sh
import shutil

from dlrn.config import getConfigOptions

logger = logging.getLogger("dlrn-repositories")


def refreshrepo(url, path, branch="master", local=False, full_path=None):
    config_options = getConfigOptions()
    logger.info("Getting %s to %s (%s)" % (url, path, branch))
    checkout_not_present = not os.path.exists(path)
    if checkout_not_present is True:
        try:
            sh.git.clone(url, path)
        except Exception as e:
            logger.error("Error cloning %s into %s: %s" % (url, path, e))
            raise

    elif local is False:
        # We need to cover a corner case here, where the repo URL has changed
        # since the last execution
        git = sh.git.bake(_cwd=path, _tty_out=False, _timeout=3600)
        try:
            remotes = git("remote", "-v").splitlines()
            fetch_url = None
            for remote in remotes:
                if '(fetch)' in remote:
                    line = remote.split()
                    if line[1] == url:
                        break
                    else:
                        fetch_url = line[1]
            else:
                # URL changed, so remove directory
                logger.warning("URL for %s changed from %s to %s, "
                               "cleaning directory and cloning again"
                               % (path, fetch_url, url))
                shutil.rmtree(path, ignore_errors=True)
                try:
                    sh.git.clone(url, path)
                except Exception as e:
                    logger.error("Error cloning %s into %s: %s" % (url, path,
                                                                   e))
                    raise
        except Exception:
            # Something failed here, maybe this is a failed repo clone
            # Let's warn, remove directory and clone again
            logger.warning("Directory %s does not contain a valid Git repo, "
                           "cleaning directory and cloning again" % path)
            shutil.rmtree(path)
            sh.git.clone(url, path)

    git_path = full_path or path
    git = sh.git.bake(_cwd=git_path, _tty_out=False, _timeout=3600)

    if local is False or checkout_not_present is True:
        try:
            git.fetch("origin")
        except Exception:
            # Sometimes hg repositories get into a invalid state leaving them
            # unusable, to avoid a looping error just remove it so it will be
            # recloned.
            logger.error("Error fetching into %s, deleting." % (path))
            sh.sudo("rm", "-rf", path)
            raise
        try:
            git.checkout('-f', branch)
        except sh.ErrorReturnCode_1:
            for branch_re in config_options.nonfallback_branches:
                if re.match(branch_re, branch):
                    # Do not try fallback on selected branches
                    raise
            else:
                if config_options.fallback_to_master:
                    # Fallback to master
                    if branch.startswith("rpm-"):
                        branch = "rpm-master"
                    elif branch.endswith("-rdo"):
                        # Distgit branches can start with rpm- or end with -rdo
                        branch = "rpm-master"
                    else:
                        branch = "master"
                    logger.info("Falling back to %s" % branch)
                    git.checkout(branch)
                else:
                    logger.error("Branch %s for %s does not exist, and the "
                                 "configuration does not allow a fallback to "
                                 "master." % (branch, url))
                    raise
        try:
            git.reset("--hard", "origin/%s" % branch)
        except Exception:
            # Maybe it was a tag, not a branch
            git.reset("--hard", "%s" % branch)

    repoinfo = str(git.log("--pretty=format:%H %ct", "-1", ".")).\
        strip().split(" ")
    repoinfo.insert(0, branch)
    return repoinfo


def getdistrobranch(package):
    if 'distro-branch' in package:
        return package['distro-branch']
    else:
        config_options = getConfigOptions()
        return config_options.distro


def getsourcebranch(package):
    if 'source-branch' in package:
        return package['source-branch']
    else:
        config_options = getConfigOptions()
        return config_options.source
