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

# The GitRepoDriver provides the following:
#
# 1- A getpackages function based on finding all directories inside a specific
#    git repo, where each directory represents a package
#
# 2- A getinfo function based on a single-distgit repo paradigm
#
# 3- A preprocess function using renderspec on any *.spec.j2 file found in the
#    distgit.

import logging
import os
import re
import sh

from dlrn.db import Commit
from dlrn.drivers.pkginfo import PkgInfoDriver
from dlrn.repositories import getsourcebranch
from dlrn.repositories import refreshrepo
from dlrn.utils import run_external_preprocess
from pymod2pkg import module2package
from pymod2pkg import module2upstream
from rdopkg.utils import specfile
from six.moves import urllib
from six.moves.urllib.request import urlopen

logger = logging.getLogger("dlrn-gitrepo-driver")

version_match = re.compile(r'\W*set upstream_version\D+([\w.]+).*')
wrong_match = re.compile(r'\W*set upstream_version\D+\(\).*')

base_urls = ['https://opendev.org/openstack',
             'https://opendev.org/x',
             'https://opendev.org/opendev']


def check_url(url):
    logger.info("Checking url %s" % url)
    try:
        urlopen(url)
        # URL found
        return True
    except (urllib.error.HTTPError, urllib.error.URLError):
        # Trouble finding URL
        return False


class GitRepoDriver(PkgInfoDriver):
    DRIVER_CONFIG = {
        'gitrepo_driver': {
            'gitrepo_repo': {'name': 'repo'},
            'gitrepo_dirs': {'name': 'directory', 'type': 'list'},
            'skip_dirs': {'name': 'skip', 'type': 'list'},
            'use_version_from_spec': {'type': 'boolean'},
            'keep_tarball': {'type': 'boolean'},
        }
    }

    def __init__(self, *args, **kwargs):
        super(GitRepoDriver, self).__init__(*args, **kwargs)

    def _get_version_from_pkg(self, packagepath, package):
        self.preprocess(package_name=package)
        pkgdir = os.path.join(packagepath, package)
        for pkgfile in os.listdir(pkgdir):
            if pkgfile.endswith('.spec'):
                spec = specfile.Spec(fn=os.path.join(packagepath, package,
                                                     pkgfile))
                version = spec.get_tag('Version')
                release = spec.get_tag('Release')

        if release.startswith('0'):
            # This is a pre-release version, so we are following trunk
            return None
        else:
            # This is a tagged release
            return version

    def getpackages(self, **kwargs):
        repo = self.config_options.gitrepo_repo
        distro_branch = self.config_options.distro
        datadir = self.config_options.datadir
        skip_dirs = self.config_options.skip_dirs
        dev_mode = kwargs.get('dev_mode')
        packages = []

        gitpath = os.path.join(datadir, 'package_info')
        if not os.path.exists(gitpath):
            sh.git.clone(repo, gitpath)

        if not dev_mode:
            git = sh.git.bake(_cwd=gitpath, _tty_out=False, _timeout=3600)
            git.fetch("origin")
            # Use the the configured distro branch, fall back to master
            # if it fails
            try:
                git.reset("--hard", "origin/%s" % distro_branch)
            except Exception:
                logger.info("Falling back to master")
                git.reset("--hard", "origin/master")

        for basepath in self.config_options.gitrepo_dirs:
            path = basepath.strip('/')
            packagepath = os.path.join(gitpath, path)

            for package in os.listdir(packagepath):
                if (os.path.isdir(os.path.join(packagepath, package)) and
                   package not in skip_dirs):
                    pkg_hash = {}
                    pkg_hash['name'] = package
                    pkg_hash['maintainers'] = 'test@example.com'
                    pkg_hash['master-distgit'] = (repo + '/' + path + '/' +
                                                  package)
                    pkg_hash['upstream'] = 'Unknown'
                    if self.config_options.use_version_from_spec is True:
                        version = None
                        # Try to deduce version from spec template
                        pkgdir = os.path.join(packagepath, package)
                        for pkgfile in os.listdir(pkgdir):
                            if pkgfile.endswith('.j2'):
                                with open(os.path.join(pkgdir, pkgfile)) as fp:
                                    j2content = fp.readlines()
                                for line in j2content:
                                    # Make sure we are not matching the wrong
                                    # version of the upstream_version() macro
                                    m = wrong_match.match(line)
                                    if m is not None:
                                        # We are deducing the version using
                                        # the source tarball. This is a bit
                                        # mroe complex, since we need to run
                                        # renderspec and find the version in
                                        # the resulting spec
                                        version = self._get_version_from_pkg(
                                            packagepath, package)
                                        logger.info(
                                            "Got version %s for %s from the "
                                            "spec" % (version, package))
                                        break
                                    # Does template define upstream_version?
                                    m = version_match.match(line)
                                    if m is not None:
                                        version = m.group(1)
                                        break
                                    # Otherwise, we're using a direct version
                                    if line.startswith('Version:'):
                                        version = line.split(':')[1].strip().\
                                            replace('~', '')
                                        break

                        if version is not None:
                            pkg_hash['source-branch'] = version
                    packages.append(pkg_hash)
        return packages

    def getinfo(self, **kwargs):
        project = kwargs.get('project')
        package = kwargs.get('package')
        since = kwargs.get('since')
        local = kwargs.get('local')
        dev_mode = kwargs.get('dev_mode')
        datadir = self.config_options.datadir

        for url in base_urls:
            if check_url("%s/%s" % (url, module2upstream(package['name']))):
                package['upstream'] = ("%s/%s" %
                                       (url,
                                        module2upstream(package['name'])))
                break
        else:
            logger.error("Could not find upstream URL for project %s" %
                         package)

        repo = package['upstream']

        distro_dir = self.distgit_dir(package['name'])
        source_branch = getsourcebranch(package)

        if dev_mode is True:
            distro_hash = "dev"
            dt_distro = 0  # Doesn't get used in dev mode
        else:
            # Get distro_hash from last commit in distgit directory
            git = sh.git.bake(_cwd=distro_dir, _tty_out=False)
            repoinfo = str(git.log("--pretty=format:%H %ct", "-1", ".")
                           ).strip().split(" ")
            distro_hash = repoinfo[0]
            dt_distro = repoinfo[1]

        # repo is usually a string, but if it contains more then one entry we
        # git clone into a project subdirectory
        repos = [repo]
        if isinstance(repo, list):
            repos = repo
        project_toprocess = []
        for repo in repos:
            repo_dir = os.path.join(datadir, project)
            if len(repos) > 1:
                repo_dir = os.path.join(repo_dir, os.path.split(repo)[1])
            try:
                source_branch, _, _ = refreshrepo(repo, repo_dir,
                                                  source_branch, local=local)
            except Exception:
                # The error was already logged by refreshrepo, and the only
                # side-effect is that we are not adding this commit to the
                # list of commits to be processed, so we can ignore it and
                # move on to the next repo
                return PkgInfoDriver.Info([], True)

            git = sh.git.bake(_cwd=repo_dir, _tty_out=False)
            # Git gives us commits already sorted in the right order
            lines = git.log("--pretty=format:'%ct %H'", since,
                            "--first-parent", "--reverse")

            for line in lines:
                dt, commit_hash = str(line).strip().strip("'").split(" ")
                commit = Commit(dt_commit=float(dt), project_name=project,
                                type='rpm',
                                commit_hash=commit_hash, repo_dir=repo_dir,
                                distro_hash=distro_hash, dt_distro=dt_distro,
                                distgit_dir=distro_dir,
                                commit_branch=source_branch,
                                dt_extended=0, extended_hash=None,
                                component=None)
                project_toprocess.append(commit)

        return PkgInfoDriver.Info(project_toprocess, False)

    def preprocess(self, **kwargs):
        package_name = kwargs.get('package_name')
        commit_hash = kwargs.get('commit_hash')
        distgit_dir = self.distgit_dir(package_name)
        output_filename = "%s.spec" % module2package(package_name, 'fedora')
        source_dir = "%s/%s" % (self.config_options.datadir, package_name)
        preprocess = sh.renderspec.bake(_cwd=distgit_dir,
                                        _tty_out=False, _timeout=3600)
        preprocess('--spec-style', 'fedora', '--epoch',
                   '../../epoch/fedora.yaml', '--output', output_filename)
        # Replace %{version} with %{upstream_version} in spec
        # This is required by rpm-packaging specs
        for specf in os.listdir(distgit_dir):
            if specf.endswith(".spec"):
                filename = os.path.join(distgit_dir, specf)
                with open(filename, 'r+') as fp:
                    spec = fp.read()
                    spec = re.sub(r'-%{version}', '-%{upstream_version}', spec)
                    fp.seek(0)
                    fp.write(spec)

        for custom_preprocess in self.config_options.custom_preprocess:
            if custom_preprocess != '':
                run_external_preprocess(
                    cmdline=custom_preprocess,
                    pkgname=package_name,
                    distgit=distgit_dir,
                    source_dir=source_dir,
                    commit_hash=commit_hash)

    def distgit_dir(self, package_name):
        datadir = self.config_options.datadir
        # Check all potential base directories
        for basepath in self.config_options.gitrepo_dirs:
            path = basepath.strip('/')
            fullpath = os.path.join(datadir, 'package_info', path,
                                    package_name)
            if os.path.exists(fullpath):
                return fullpath
