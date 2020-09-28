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
import sh

from dlrn.config import getConfigOptions

logger = logging.getLogger("dlrn-rsync")


def sync_repo(commit):
    config_options = getConfigOptions()
    rsyncdest = config_options.rsyncdest
    rsyncport = config_options.rsyncport
    datadir = os.path.realpath(config_options.datadir)

    if rsyncdest != '':
        # We are only rsyncing the current repo dir to rsyncdest
        rsyncpaths = []
        # We are inserting a dot in the path after repos, this is used by
        # rsync -R (see man rsync)
        commitdir_abs = os.path.join(datadir, "repos", ".",
                                     commit.getshardedcommitdir())
        rsyncpaths.append(commitdir_abs)
        # We also need report.html, status_report.html, queue.html,
        # styles.css and the consistent and current symlinks
        for filename in ['report.html', 'status_report.html', 'styles.css',
                         'queue.html', 'status_report.csv']:
            filepath = os.path.join(datadir, "repos", ".", filename)
            rsyncpaths.append(filepath)

        rsh_command = 'ssh -p %s -o StrictHostKeyChecking=no' % rsyncport
        try:
            sh.rsync('-avzR', '--delete-delay',
                     '-e', rsh_command,
                     rsyncpaths, rsyncdest)
        except Exception as e:
            logger.warn('Failed to rsync content to %s ,'
                        'got error %s' % (rsyncdest, e))
            # Raise exception, so it can be treated as an error
            raise e


def sync_symlinks(commit):
    config_options = getConfigOptions()
    rsyncdest = config_options.rsyncdest
    rsyncport = config_options.rsyncport
    datadir = os.path.realpath(config_options.datadir)
    reponame = config_options.reponame

    if rsyncdest != '':
        # We want to sync the symlinks in a second pass, once all content
        # has been copied, to avoid a race condition it they are copied first
        rsyncpaths = []
        for filename in ['consistent', 'current']:
            if config_options.use_components:
                filepath = os.path.join(datadir, "repos", ".", "component",
                                        commit.component, filename)
            else:
                filepath = os.path.join(datadir, "repos", ".", filename)
            rsyncpaths.append(filepath)

        # If using components, current and consistent on the top-level dir
        # are not symlinks, but full directories

        if config_options.use_components:
            exclude_list = []
            extra_include_list = []
            for filename in ['consistent', 'current']:
                filepath = os.path.join(datadir, "repos", ".", filename)
                rsyncpaths.append(filepath)

                exclude_list.extend(['--exclude', '%s/%s.repo' %
                                     (filename, reponame)])
                exclude_list.extend(['--exclude', '%s/%s.repo.md5' %
                                     (filename, reponame)])
                exclude_list.extend(['--exclude', '%s/versions.csv' %
                                    filename])
                extra_include_list.append('%s/%s.repo' % (filepath, reponame))
                extra_include_list.append('%s/%s.repo.md5' %
                                          (filepath, reponame))
                extra_include_list.append('%s/versions.csv' % filepath)

        rsh_command = 'ssh -p %s -o StrictHostKeyChecking=no' % rsyncport

        if config_options.use_components:
            try:
                # First, rsync everything except the top-level symlinks
                sh.rsync('-avzR', '--delete-delay',
                         '-e', rsh_command,
                         exclude_list,
                         rsyncpaths, rsyncdest)
            except Exception as e:
                # We are not raising exceptions for symlink rsyncs, these will
                # be fixed after another build
                logger.warn('Failed to rsync symlinks to %s ,'
                            'got error %s' % (rsyncdest, e))
            try:
                # Then, the top-level symlinks
                sh.rsync('-avzR', '--delete-delay',
                         '-e', rsh_command,
                         extra_include_list, rsyncdest)
            except Exception as e:
                # We are not raising exceptions for symlink rsyncs, these will
                # be fixed after another build
                logger.warn('Failed to rsync symlinks to %s ,'
                            'got error %s' % (rsyncdest, e))
        else:
            try:
                sh.rsync('-avzR', '--delete-delay',
                         '-e', rsh_command,
                         rsyncpaths, rsyncdest)
            except Exception as e:
                # We are not raising exceptions for symlink rsyncs, these will
                # be fixed after another build
                logger.warn('Failed to rsync symlinks to %s ,'
                            'got error %s' % (rsyncdest, e))
