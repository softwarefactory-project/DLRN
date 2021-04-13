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


from dlrn.db import Commit
from dlrn.drivers.pkginfo import PkgInfoDriver
from dlrn.repositories import getdistrobranch
from dlrn.repositories import getsourcebranch
from dlrn.repositories import refreshrepo
from dlrn.utils import run_external_preprocess

import csv
import logging
import os
import re
import sh
import shutil

from contextlib import closing
from distroinfo import info
from distroinfo import query
from six.moves.urllib.request import urlopen


logger = logging.getLogger("dlrn-downstream-driver")


def fail_req_attr_missing(attr_name, package):
    raise Exception(
        "Missing required attribute '%s' "
        "for package: %s (project: %s)" % (
            attr_name, package['project'], package['name']))


def fail_req_config_missing(opt_name):
    raise Exception(
        "Missing required config option '%s' "
        "for dlrn.drivers.downstream driver." % opt_name)


class DownstreamInfoDriver(PkgInfoDriver):
    DRIVER_CONFIG = {
        'downstream_driver': {
            'rdoinfo_repo': {'name': 'repo'},
            'info_files': {'type': 'list'},
            'versions_url': {},
            'downstream_distro_branch': {},
            'downstream_tag': {},
            'downstream_distgit_key': {},
            'downstream_source_git_key': {},
            'downstream_source_git_branch': {},
            'use_upstream_spec': {'type': 'boolean'},
            'downstream_spec_replace_list': {'type': 'list'},
            'cache_dir': {},
        }
    }

    def __init__(self, *args, **kwargs):
        super(DownstreamInfoDriver, self).__init__(*args, **kwargs)
        self.distroinfo_path = None

    def getpackages(self, **kwargs):
        """Valid parameters:

        :param local_info_repo: local rdoinfo repo to use instead of fetching
                                the default one using distroinfo.
        :param tags: release tags to use (mitaka, newton, etc).
        """
        local_info_repo = kwargs.get('local_info_repo')
        tags = kwargs.get('tags')

        info_files = self.config_options.info_files
        if not info_files:
            fail_req_config_missing('info_file')

        inforepo = None
        if local_info_repo:
            inforepo = info.DistroInfo(
                info_files=info_files,
                local_info=local_info_repo,
                cache_base_path=self.config_options.cache_dir)
            # NOTE(jpena): in general, info_files will only contain one file,
            # but it supports multiple... In that case, we will have a comma
            # separated list of URLs
            self.distroinfo_path = "%s/%s" % (local_info_repo.rstrip('/'),
                                              info_files[0])
            for extra_file in info_files[1:]:
                self.distroinfo_path += ",%s/%s" % (
                    local_info_repo.rstrip('/'))

        elif self.config_options.rdoinfo_repo:
            inforepo = info.DistroInfo(
                info_files=info_files,
                remote_git_info=self.config_options.rdoinfo_repo,
                cache_base_path=self.config_options.cache_dir)
            rdoinfo_repo = self.config_options.rdoinfo_repo
            self.distroinfo_path = "%s/%s" % (rdoinfo_repo.rstrip('/'),
                                              info_files[0])
            for extra_file in info_files[1:]:
                self.distroinfo_path += ",%s/%s" % (
                    rdoinfo_repo.rstrip('/'), extra_file)

        else:
            fail_req_config_missing('repo')
        pkginfo = inforepo.get_info(apply_tag=tags)

        self.packages = pkginfo["packages"]
        if tags:
            # FIXME allow list of tags?
            self.packages = query.filter_pkgs(self.packages, {'tags': tags})

        if self.config_options.downstream_tag:
            # filter out packages missing parameters with
            # downstream_tag
            downstream_tag = self.config_options.downstream_tag
            self.packages = query.filter_pkgs(
                self.packages,
                {'tags': downstream_tag})
        return self.packages

    def _getversions(self):
        """Fetch 'versions.csv'

        from versions_url config option and return the contained data as
        a dict with package name as a key.
        """
        versions_url = self.config_options.versions_url
        if not versions_url:
            fail_req_config_missing('versions_url')

        # return versions.csv as a dict with package name as a key
        vers = {}
        with closing(urlopen(versions_url)) as r:
            content = [x.decode('utf-8') for x in r.readlines()]
        # first line is headers
        for row in csv.reader(content[1:]):
            vers[row[0]] = row[1:]
        return vers

    def _fetch_reference_commit(self):
        """Fetch the commit.yaml file used for this run

        """
        versions_url = self.config_options.versions_url
        commit_url = re.sub('/versions.csv$', '/commit.yaml', versions_url)
        try:
            with closing(urlopen(commit_url)) as r:
                content = [x.decode('utf-8') for x in r.readlines()]
            return content
        except Exception:
            # We do not want to fail on this
            return None

    def _write_reference_commit(self, directory):
        """Write the commit.yaml file

        Used for this run in directory as reference_commit.yaml

        :param: directory where the file will be stored
        """

        ref_commit_yaml = self._fetch_reference_commit()

        if ref_commit_yaml is None:
            return
        path = os.path.join(directory, 'reference_commit.yaml')
        with open(path, 'w') as fp:
            for line in ref_commit_yaml:
                fp.write(line)

    def _transform_spec(self, directory):
        """Transform based on rules, basically a crude sed implementation

        :param directory: directory to search the spec on
        """
        for f in os.listdir(directory):
            if f.endswith('.spec'):
                specpath = os.path.join(directory, f)
                with open(specpath, "r") as fp:
                    contents = fp.readlines()
                with open(specpath, "w") as fp:
                    for line in contents:
                        for rule in self.config_options.\
                            downstream_spec_replace_list:
                            src = rule.split('/')[0]
                            dst = rule.split('/')[1]
                            line = re.sub(src, dst, line)
                        fp.write(line)

    def getinfo(self, **kwargs):
        project = kwargs.get('project')
        package = kwargs.get('package')
        local = kwargs.get('local')
        dev_mode = kwargs.get('dev_mode')

        datadir = self.config_options.datadir
        repo = package['upstream']
        distgit_attr = self.config_options.downstream_distgit_key or 'distgit'
        distro = package.get(distgit_attr)
        if not distro:
            fail_req_attr_missing(distgit_attr, package)
        distro_dir = self._distgit_clone_dir(package['name'])
        distro_dir_full = self.distgit_dir(package['name'])
        distro_branch = self.config_options.downstream_distro_branch
        if not distro_branch:
            fail_req_config_missing('downstream_distro_branch')
        source_branch = getsourcebranch(package)
        versions = self._getversions()

        ups_distro = package['master-distgit']
        ups_distro_dir = self._upstream_distgit_clone_dir(package['name'])
        ups_distro_dir_full = self.upstream_distgit_dir(package['name'])
        ups_distro_branch = getdistrobranch(package)

        # Downstream source git
        dsgit_attr = self.config_options.downstream_source_git_key
        ds_source = package.get(dsgit_attr)
        if not distro:
            fail_req_attr_missing(dsgit_attr, package)
        dsgit_dir = self._downstream_git_clone_dir(package['name'])
        dsgit_branch = self.config_options.downstream_source_git_branch

        # only process packages present in versions.csv
        if package['name'] not in versions:
            logger.warning('Package %s not present in %s - skipping.' % (
                package['name'], self.config_options.versions_url))
            return PkgInfoDriver.Info([], True)
        version = versions[package['name']]

        dt_distro = 0  # In this driver we do not care about dt_distro

        if dev_mode is False:
            try:
                distro_branch, extended_hash_dsdist, dt_extended = refreshrepo(
                    distro, distro_dir, distro_branch, local=local,
                    full_path=distro_dir_full)

                _, extended_hash_dssource, _ = refreshrepo(
                    ds_source, dsgit_dir, dsgit_branch, local=local,
                    full_path=dsgit_dir)

                extended_hash = '%s_%s' % (extended_hash_dsdist,
                                           extended_hash_dssource)

                # extract distro_hash from versions.csv
                distro_hash = version[3]
                # Also download upstream distgit
                _, _, _ = refreshrepo(
                    ups_distro, ups_distro_dir, distro_hash,
                    local=local, full_path=ups_distro_dir_full)

            except Exception:
                # The error was already logged by refreshrepo, and we want
                # to avoid halting the whole run because this distgit repo
                # failed, so return an empty list
                return PkgInfoDriver.Info([], True)
        else:
            distro_hash = "dev"
            extended_hash = "dev"
            dt_extended = 0
            if not os.path.isdir(distro_dir):
                # We should fail in this case, since we are running
                # in dev mode, so no try/except
                refreshrepo(distro, distro_dir, distro_branch, local=local,
                            full_path=distro_dir_full)
            if not os.path.isdir(ups_distro_dir):
                refreshrepo(ups_distro, ups_distro_dir, ups_distro_branch,
                            local=local, full_path=ups_distro_dir_full)

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
                                                  source_branch,
                                                  local=local)
            except Exception:
                # The error was already logged by refreshrepo, and the only
                # side-effect is that we are not adding this commit to the
                # list of commits to be processed, so we can ignore it and
                # move on to the next repo
                return PkgInfoDriver.Info([], True)
            if not local:
                # This is the default behavior
                dt = version[5]
                commit_hash = version[1]
            else:
                # When running with --local, we really want to use the local
                # source git, regardless of the upstream versions.csv info
                git = sh.git.bake(_cwd=repo_dir, _tty_out=False)
                lines = git.log("--pretty=format:'%ct %H'",
                                "-1", "--first-parent",
                                "--reverse")
                for line in lines:
                    # There is only one line
                    dt, commit_hash = str(line).strip().strip("'").\
                                        split(" ")[:2]

            if self.config_options.use_components and 'component' in package:
                component = package['component']
            else:
                component = None
            commit = Commit(dt_commit=float(dt), project_name=project,
                            type='rpm',
                            commit_hash=commit_hash, repo_dir=repo_dir,
                            distro_hash=distro_hash, dt_distro=dt_distro,
                            extended_hash=extended_hash,
                            dt_extended=dt_extended,
                            distgit_dir=self.distgit_dir(package['name']),
                            commit_branch=source_branch, component=component)
            project_toprocess.append(commit)

        return PkgInfoDriver.Info(project_toprocess, False)

    def preprocess(self, **kwargs):
        package_name = kwargs.get('package_name')
        commit_hash = kwargs.get('commit_hash')
        distgit_dir = self.distgit_dir(package_name)
        ups_distro_dir_full = self.upstream_distgit_dir(package_name)
        distro_dir_full = self.distgit_dir(package_name)
        datadir = os.path.realpath(self.config_options.datadir)
        source_dir = "%s/%s" % (self.config_options.datadir, package_name)

        # In this case, we will copy the upstream distgit into downstream
        # distgit, then transform spec
        if self.config_options.use_upstream_spec:
            if self.config_options.keep_changelog:
                # Save the existing changelog
                changelog = self._save_changelog(distgit_dir)
            # Copy upstream distgit to downstream distgit
            for f in os.listdir(ups_distro_dir_full):
                # skip hidden files
                if not f.startswith('.'):
                    shutil.copy(os.path.join(ups_distro_dir_full, f),
                                distro_dir_full)

            if len(self.config_options.downstream_spec_replace_list) > 0:
                self._transform_spec(distro_dir_full)

            if self.config_options.keep_changelog:
                # Restore the old changelog, instead of replacing it with
                # the upstream one
                self._restore_changelog(distgit_dir, changelog)
        # If we have a jinja2 spec template, run pre-processing
        preprocess_needed = False
        for f in os.listdir(distgit_dir):
            if f.endswith('.spec.j2'):
                # We have a template here, so we have to preprocess
                preprocess_needed = True
                break
        if preprocess_needed:
            logger.info('Pre-processing template at %s' % distgit_dir)
            renderspec = sh.renderspec.bake(_cwd=distgit_dir,
                                            _tty_out=False, _timeout=3600)
            renderspec('--spec-style', 'fedora', '--epoch',
                       '../../epoch/fedora.yaml')

        for custom_preprocess in self.config_options.custom_preprocess:
            if custom_preprocess != '':
                run_external_preprocess(
                    cmdline=custom_preprocess,
                    pkgname=package_name,
                    distgit=distgit_dir,
                    upstream_distgit=ups_distro_dir_full,
                    distroinfo=self.distroinfo_path,
                    source_dir=source_dir,
                    commit_hash=commit_hash,
                    datadir=datadir)
        return

    def distgit_dir(self, package_name):
        datadir = self.config_options.datadir
        # Find extra directory inside it, if needed
        extra_dir = '/'
        for package in self.packages:
            if package['name'] == package_name:
                if 'distgit-path' in package:
                    extra_dir = package['distgit-path']
                    break
        return os.path.join(datadir, package_name + "_distro",
                            extra_dir.lstrip('/'))

    def _distgit_clone_dir(self, package_name):
        datadir = self.config_options.datadir
        return os.path.join(datadir, package_name + "_distro")

    def _downstream_git_clone_dir(self, package_name):
        datadir = self.config_options.datadir
        return os.path.join(datadir, package_name + "_downstream")

    def upstream_distgit_dir(self, package_name):
        datadir = self.config_options.datadir
        # Find extra directory inside it, if needed
        extra_dir = '/'
        for package in self.packages:
            if package['name'] == package_name:
                if 'distgit-path' in package:
                    extra_dir = package['distgit-path']
                    break
        return os.path.join(datadir, package_name + "_distro_upstream",
                            extra_dir.lstrip('/'))

    def _upstream_distgit_clone_dir(self, package_name):
        datadir = self.config_options.datadir
        return os.path.join(datadir, package_name + "_distro_upstream")

    def _save_changelog(self, distgit_dir):
        changelog = ''
        spec = None
        for f in os.listdir(distgit_dir):
            if f.endswith('.spec'):
                with open(os.path.join(distgit_dir, f)) as fp:
                    spec = fp.read()
                    # This will read everything from a line starting with
                    # %changelog, till the end of file
                    match = re.search(r'^%changelog.*', spec,
                                      flags=(re.MULTILINE | re.DOTALL))
                    if match:
                        changelog = match.group()

        return changelog

    def _restore_changelog(self, distgit_dir, changelog):
        for f in os.listdir(distgit_dir):
            if f.endswith('.spec'):
                with open(os.path.join(distgit_dir, f)) as fp:
                    spec = fp.read()
                # Replace the %changelog part with the saved changelog
                newspec = re.sub(r'^%changelog.*',
                                 changelog,
                                 spec,
                                 flags=(re.MULTILINE | re.DOTALL))
                with open(os.path.join(distgit_dir, f), 'w') as fp:
                    fp.write(newspec)
