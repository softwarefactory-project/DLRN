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

import os
import sh

from dlrn.db import Commit
from dlrn.drivers.pkginfo import PkgInfoDriver
from dlrn.shell import config_options
from dlrn.shell import getsourcebranch
from dlrn.shell import refreshrepo


class GitRepoDriver(PkgInfoDriver):

    def __init__(self, *args, **kwargs):
        super(GitRepoDriver, self).__init__(*args, **kwargs)

    def getpackages(self, **kwargs):
        repo = config_options.gitrepo_repo
        path = config_options.gitrepo_dir.strip('/')
        datadir = config_options.datadir
        skip_dirs = config_options.skip_dirs
        dev_mode = kwargs.get('dev_mode')
        packages = []

        gitpath = os.path.join(datadir, 'package_info')
        if not os.path.exists(gitpath):
            sh.git.clone(repo, gitpath)

        if not dev_mode:
            git = sh.git.bake(_cwd=gitpath, _tty_out=False, _timeout=3600)
            git.fetch("origin")
            # TODO(jpena): allow passing a branch as argument
            git.reset("--hard", "origin/master")

        packagepath = os.path.join(gitpath, path)

        for package in os.listdir(packagepath):
            if (os.path.isdir(os.path.join(packagepath, package)) and
               package not in skip_dirs):
                pkg_hash = {}
                if package in config_options.subst_hash:
                    pkg_name = config_options.subst_hash[package]
                else:
                    pkg_name = package

                pkg_hash['name'] = package
                pkg_hash['upstream'] = ('https://github.com/openstack/' +
                                        pkg_name)
                pkg_hash['maintainers'] = 'test@example.com'
                pkg_hash['master-distgit'] = (repo + '/' + path + '/' +
                                              package)
                if config_options.use_version_from_spec is True:
                    version = None
                    # Try to deduce version from spec template
                    pkgdir = os.path.join(packagepath, package)
                    for pkgfile in os.listdir(pkgdir):
                        if pkgfile.endswith('.j2'):
                            with open(os.path.join(pkgdir, pkgfile)) as fp:
                                j2content = fp.readlines()
                            for line in j2content:
                                if line.startswith('Version:'):
                                    version = line.split(':')[1].strip().\
                                        replace('~', '')

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
        datadir = config_options.datadir
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
            source_branch, _, _ = refreshrepo(repo, repo_dir, source_branch,
                                              local=local)

            git = sh.git.bake(_cwd=repo_dir, _tty_out=False)
            # Git gives us commits already sorted in the right order
            lines = git.log("--pretty=format:'%ct %H'", since,
                            "--first-parent", "--reverse")

            for line in lines:
                dt, commit_hash = str(line).strip().strip("'").split(" ")
                commit = Commit(dt_commit=float(dt), project_name=project,
                                commit_hash=commit_hash, repo_dir=repo_dir,
                                distro_hash=distro_hash, dt_distro=dt_distro,
                                distgit_dir=distro_dir)
                project_toprocess.append(commit)

        return project_toprocess

    def preprocess(self, **kwargs):
        package_name = kwargs.get('package_name')
        distgit_dir = self.distgit_dir(package_name)
        preprocess = sh.renderspec.bake(_cwd=distgit_dir,
                                        _tty_out=False, _timeout=3600)
        preprocess('--spec-style', 'fedora')

    def distgit_dir(self, package_name):
        datadir = config_options.datadir
        path = config_options.gitrepo_dir.strip('/')
        return os.path.join(datadir, 'package_info', path, package_name)
