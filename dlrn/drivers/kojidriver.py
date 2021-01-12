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
import multiprocessing
import os
import re
import sh

from time import localtime
from time import strftime
from time import time

logger = logging.getLogger("dlrn-build-koji")


class KojiBuildDriver(BuildRPMDriver):
    DRIVER_CONFIG = {
        'kojibuild_driver': {
            'koji_krb_principal': {'name': 'krb_principal'},
            'koji_krb_keytab': {'name': 'krb_keytab'},
            'koji_scratch_build': {'name': 'scratch_build', 'type': 'boolean',
                                   'default': True},
            'koji_build_target': {'name': 'build_target'},
            'koji_arch': {'name': 'arch', 'default': 'x86_64'},
            'koji_use_rhpkg': {'name': 'use_rhpkg', 'type': 'boolean'},
            'koji_exe': {'default': 'koji'},
            'fetch_mock_config': {'type': 'boolean'},
            'mock_base_packages': {'default': ''},
            'mock_package_manager': {'default': ''},
            'koji_add_tags': {'name': 'additional_koji_tags', 'type': 'list',
                              'default': []},
        }
    }

    def __init__(self, *args, **kwargs):
        super(KojiBuildDriver, self).__init__(*args, **kwargs)
        self.exe_name = self.config_options.koji_exe
        # Check for empty additional_koji_tags value
        if self.config_options.koji_add_tags == ['']:
            self.config_options.koji_add_tags = []

    # We are using this method to "tee" koji output to a log file and stdout
    def _process_koji_output(self, line):
        if dlrn.shell.verbose_build:
            logger.info(line[:-1])
        self.koji_fp.write(line)

    def write_mock_config(self, filename):
        """Retrieve mock config from Koji instance

        :param filename: output filename to write mock config
        """
        target = self.config_options.koji_build_target
        arch = self.config_options.koji_arch
        try:
            worker_id = multiprocessing.current_process()._identity[0]
        except IndexError:
            # Not in multiprocessing mode
            worker_id = 1
        run_cmd = [self.exe_name]
        run_cmd.extend(['mock-config',
                        '--arch', arch, '--target', target, '-o', filename])
        # FIXME(hguemar): add proper exception management
        sh.env(run_cmd,
               _env={'PATH': '/usr/bin/'})
        lines = []
        with open(filename, 'r') as fp:
            for line in fp.readlines():
                if (line.startswith("config_opts['chroot_setup_cmd']") and
                        self.config_options.mock_base_packages != ''):
                    lines.append("config_opts['chroot_setup_cmd'] = "
                                 "'install %s'\n" %
                                 self.config_options.mock_base_packages)
                elif line.startswith("config_opts['root']"):
                    # Append worker id to mock buildroot name
                    line = line[:-2] + "-" + str(worker_id) + "'\n"
                    lines.append(line)
                else:
                    lines.append(line)
            if self.config_options.mock_package_manager:
                lines.append("config_opts['package_manager'] = '%s'\n" %
                             self.config_options.mock_package_manager)
        with open(filename, 'w') as fp:
            fp.write(''.join(lines))

    def _build_with_rhpkg(self, package_name, output_dir, src_rpm, scratch,
                          commit):
        """Use rhpkg as build backend

        :param package_name: package name to build
        :param output_dir: output directory
        :param src_rpm: source RPM to build
        :param scratch: define if build is scratch or not
        """
        distgit_dir = os.path.join(
            self.config_options.datadir,
            package_name + "_distro")

        ds_source_git = os.path.join(
            self.config_options.datadir,
            package_name + "_downstream")

        build_exception = None

        # if we are using rhpkg, we need to create a kerberos ticket
        krb_principal = self.config_options.koji_krb_principal
        keytab_file = self.config_options.koji_krb_keytab
        with io.open("%s/kerberos.log" % output_dir, 'a',
                     encoding='utf-8', errors='replace') as self.koji_fp:
            sh.kinit('-k', '-t', keytab_file, krb_principal)

        rhpkg = sh.rhpkg.bake(_cwd=distgit_dir, _tty_out=False,
                              _timeout=3600,
                              _err=self._process_koji_output,
                              _out=self._process_koji_output,
                              _env={'PATH': '/usr/bin/'})

        if (self.config_options.pkginfo_driver ==
            'dlrn.drivers.downstream.DownstreamInfoDriver' and
                self.config_options.use_upstream_spec):
            # This is a special situation. We are copying the upstream
            # spec over, but then building the srpm and importing. In this
            # situation, rhpkg import will complain because there are
            # uncommited changes to the repo... and we will commit them
            # the srpm. So let's reset the git repo right before that.
            git = sh.git.bake(_cwd=distgit_dir, _tty_out=False,
                              _timeout=3600,
                              _err=self._process_koji_output,
                              _out=self._process_koji_output,
                              _env={'PATH': '/usr/bin/'})
            git.checkout('--', '*')

        with io.open("%s/rhpkgimport.log" % output_dir, 'a',
                     encoding='utf-8', errors='replace') as self.koji_fp:
            rhpkg('import', '--skip-diff', src_rpm)
            # Get build NVR
            m = re.search(r'([0-9a-zA-Z._+-]+)\.src\.rpm', src_rpm)
            if m and m.group(1):
                package_nvr = m.group(1)
            else:
                package_nvr = 'XXX-XXX'

            pkg_date = strftime("%Y-%m-%d-%H%M%S", localtime(time()))
            rhpkg('commit', '-p', '-m',
                  'DLRN build at %s\n\nSource SHA: %s\nDist SHA: %s\n'
                  'NVR: %s\n' %
                  (pkg_date, commit.commit_hash, commit.distro_hash,
                   package_nvr))

        # After running rhpkg commit, we have a different commit hash, so
        # let's update it
        git = sh.git.bake(_cwd=distgit_dir, _tty_out=False, _timeout=3600)
        repoinfo = str(git.log("--pretty=format:%H %ct", "-1", ".")).\
            strip().split(" ")

        if (self.config_options.pkginfo_driver ==
                'dlrn.drivers.downstream.DownstreamInfoDriver'):
            git = sh.git.bake(_cwd=ds_source_git, _tty_out=False,
                              _timeout=3600)
            # In some cases, a patch rebasing script could update the
            # downstream source git, so we ensure we have the latest code
            git.pull()
            repoinfo_ds_git = str(git.log("--pretty=format:%H %ct",
                                          "-1", ".")).strip().split(" ")

        logger.info("Updated git: %s" % repoinfo)
        # When using rhpkg with a pkginfo driver other than downstreamdriver,
        # we want to overwrite the distro_hash instead of extended_hash.
        # Otherwise, The distgit update will trigger yet another build on
        # the next run, causing an endless loop
        if (self.config_options.pkginfo_driver !=
                'dlrn.drivers.downstream.DownstreamInfoDriver'):
            commit.distro_hash = repoinfo[0]
            commit.dt_distro = repoinfo[1]
        else:
            commit.extended_hash = '%s_%s' % (repoinfo[0], repoinfo_ds_git[0])
            commit.dt_extended = repoinfo[1]

        # Since we are changing the extended_hash, we need to rename the
        # output directory to match the updated value
        datadir = os.path.realpath(self.config_options.datadir)
        new_output_dir = os.path.join(datadir, "repos",
                                      commit.getshardedcommitdir())
        logger.info("Renaming %s to %s" % (output_dir, new_output_dir))
        os.rename(output_dir, new_output_dir)
        output_dir = new_output_dir

        with io.open("%s/rhpkgbuild.log" % output_dir, 'a',
                     encoding='utf-8', errors='replace') as self.koji_fp:
            try:
                rhpkg('build', '--skip-nvr-check', scratch=scratch)
            except Exception as e:
                build_exception = e

        return build_exception, "%s/rhpkgbuild.log" % output_dir

    def _build_with_exe(self, package_name, output_dir, src_rpm, scratch,
                        commit):
        """Build using koji/brew executables (cbs being an aliases)

        :param package_name: package name to build
        :param output_dir: output directory
        :param src_rpm: source RPM to build
        :param scratch: define if build is scratch or not
        """

        krb_principal = self.config_options.koji_krb_principal
        keytab_file = self.config_options.koji_krb_keytab
        scratch = self.config_options.koji_scratch_build
        target = self.config_options.koji_build_target

        # Build package using koji/brew
        run_cmd = [self.exe_name]
        if krb_principal:
            run_cmd.extend(['--principal', krb_principal,
                            '--keytab', keytab_file])
        run_cmd.extend(['build', '--wait',
                        target, src_rpm])

        build_exception = None
        with io.open("%s/kojibuild.log" % output_dir, 'a',
                     encoding='utf-8', errors='replace') as self.koji_fp:
            try:
                sh.env(run_cmd, _err=self._process_koji_output,
                       _out=self._process_koji_output,
                       _cwd=output_dir, scratch=scratch,
                       _env={'PATH': '/usr/bin/'})
            except Exception as e:
                build_exception = e

        return build_exception, "%s/kojibuild.log" % output_dir

    def build_package(self, **kwargs):
        """Valid parameters:

        :param output_directory: directory where the SRPM is located,
                                 and the built packages will be.
        :param package_name: name of a package to build
        """
        output_dir = kwargs.get('output_directory')
        package_name = kwargs.get('package_name')
        commit = kwargs.get('commit')
        scratch = self.config_options.koji_scratch_build
        build_exception = None

        # Find src.rpm
        for rpm in os.listdir(output_dir):
            if rpm.endswith(".src.rpm"):
                src_rpm = os.path.realpath('%s/%s' % (output_dir, rpm))
        try:
            if self.config_options.koji_use_rhpkg:
                build_method = self._build_with_rhpkg
            else:
                build_method = self._build_with_exe
            build_exception, logfile = build_method(
                package_name, output_dir, src_rpm, scratch, commit)

            if self.config_options.koji_use_rhpkg:
                # In this case, we need to re-calculate the output directory
                datadir = os.path.realpath(self.config_options.datadir)
                output_dir = os.path.join(datadir, "repos",
                                          commit.getshardedcommitdir())

            # Find task id to download logs
            with open(logfile, 'r') as fp:
                log_content = fp.readlines()
            task_id = None
            for line in log_content:
                m = re.search(r'^Created task: (\d+)$', line)
                if m:
                    logger.info("Created task id %s" % m.group(1))
                    task_id = m.group(1)
                    break

            if not task_id:
                raise Exception('Failed to find task id for the koji build')

            # Also find package name if we need to add tags
            if len(self.config_options.koji_add_tags) > 0:
                # Get build name
                m = re.search(r'([0-9a-zA-Z._+-]+)\.src\.rpm', src_rpm)
                package_nvr = None
                if m:
                    logger.info("Adding tags for %s" % m.group(1))
                    package_nvr = m.group(1)
                if not package_nvr:
                    raise Exception('Failed to find package nvr when tagging')

                for tag in self.config_options.koji_add_tags:
                    run_cmd = []
                    run_cmd.extend(
                        [self.exe_name, 'tag-build', tag, package_nvr])

                    with io.open("%s/additional_tags.log" % output_dir, 'a',
                                 encoding='utf-8',
                                 errors='replace') as self.koji_fp:
                        try:
                            sh.env(run_cmd, _err=self._process_koji_output,
                                   _out=self._process_koji_output,
                                   _cwd=output_dir, _env={'PATH': '/usr/bin/'})
                        except Exception as e:
                            raise e

            # Download build artifacts and logs
            run_cmd = []
            run_cmd.extend(
                [self.exe_name,
                 'download-task', '--logs',
                 task_id])

            with io.open("%s/build_download.log" % output_dir, 'a',
                         encoding='utf-8', errors='replace') as self.koji_fp:
                try:
                    sh.env(run_cmd, _err=self._process_koji_output,
                           _out=self._process_koji_output,
                           _cwd=output_dir, _env={'PATH': '/usr/bin/'})
                except Exception as e:
                    raise e

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
