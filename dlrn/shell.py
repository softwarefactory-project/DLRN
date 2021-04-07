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


from __future__ import print_function
import argparse
import logging
import multiprocessing
import os
import sys
import tempfile

from copy import deepcopy
from functools import cmp_to_key
from functools import partial

import sh
from six.moves import configparser

from dlrn.build import build_worker

from dlrn.config import ConfigOptions
from dlrn.config import getConfigOptions
from dlrn.config import setup_logging

from dlrn.db import CIVote
from dlrn.db import closeSession
from dlrn.db import Commit
from dlrn.db import getCommits
from dlrn.db import getLastBuiltCommit
from dlrn.db import getLastProcessedCommit
from dlrn.db import getSession
from dlrn.db import Project
from dlrn.notifications import sendnotifymail
from dlrn.notifications import submit_review
from dlrn.reporting import genreports
from dlrn.repositories import getsourcebranch
from dlrn.rpmspecfile import RpmSpecCollection
from dlrn.rpmspecfile import RpmSpecFile
from dlrn.rsync import sync_repo
from dlrn.rsync import sync_symlinks
from dlrn.utils import aggregate_repo_files
from dlrn.utils import dumpshas2file
from dlrn.utils import import_object
from dlrn.utils import isknownerror
from dlrn.utils import lock_file
from dlrn.utils import saveYAML_commit
from dlrn.utils import timesretried
from dlrn import version

logger = logging.getLogger("dlrn")


def deprecation():
    # We will still call main, but will indicate that this way of calling
    # the application will be deprecated.
    print("Using the 'delorean' command has been deprecated. Please use 'dlrn'"
          " instead.")
    main()


def _add_commits(project_toprocess, toprocess, options, session):
    # The first entry in the list of commits is a commit we have
    # already processed, we want to process it again only if in dev
    # mode or distro hash has changed, we can't simply check
    # against the last commit in the db, as multiple commits can
    # have the same commit date
    for commit_toprocess in project_toprocess:
        # We are adding an extra check here to cover a rare corner case:
        # if we have two commits A and B with the exact same dt_commit, in a
        # first pass we will build either just the last one (if we switched
        # tags), or both. If we built the last one (A), we do not want to
        # build the other (B), because B would be a previous commit.
        # The only way to prevent this is to check that we have not built a
        # commit with the same dt_commit and same distro and extended hashes.
        # This could only be an issue if, for some reason, we want to discard
        # commit A and build commit B in the future, but we can work around
        # this by adding a change to the distgit.
        if options.dev is True or \
           options.run or \
           (not session.query(Commit).filter(
                Commit.commit_hash == commit_toprocess.commit_hash,
                Commit.distro_hash == commit_toprocess.distro_hash,
                Commit.extended_hash == commit_toprocess.extended_hash,
                Commit.type == commit_toprocess.type,
                Commit.status != "RETRY").all()
            and not session.query(Commit).filter(
                Commit.dt_commit == commit_toprocess.dt_commit,
                Commit.distro_hash == commit_toprocess.distro_hash,
                Commit.extended_hash == commit_toprocess.extended_hash,
                Commit.type == commit_toprocess.type,
                Commit.status != "RETRY").all()):
            toprocess.append(commit_toprocess)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('--config-file',
                        default='projects.ini',
                        help="Config file. Default: projects.ini")
    parser.add_argument('--config-override', action='append',
                        help="Override a configuration option from the"
                             " config file. Specify it as: "
                             "section.option=value. Can be used multiple "
                             "times if more than one override is needed.")
    parser.add_argument('--info-repo',
                        help="use a local distroinfo repo instead of"
                             " fetching the default one. Only applies when"
                             " pkginfo_driver is rdoinfo or downstream in"
                             " projects.ini")
    parser.add_argument('--build-env', action='append',
                        help="Variables for the build environment.")
    parser.add_argument('--local', action="store_true",
                        help="Use local git repos if possible. Only commited"
                             " changes in the local repo will be used in the"
                             " build.")
    parser.add_argument('--head-only', action="store_true",
                        help="Build from the most recent Git commit only.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--project-name', action='append',
                       help="Build a specific project name only."
                            " Use multiple times to build more than one "
                            "project in a run.")
    group.add_argument('--package-name', action='append',
                       help="Build a specific package name only."
                            " Use multiple times to build more than one "
                            "package in a run.")
    parser.add_argument('--dev', action="store_true",
                        help="Don't reset packaging git repo, force build "
                             "and add public master repo for dependencies "
                             "(dev mode).")
    parser.add_argument('--log-commands', action="store_true",
                        help="Log the commands run by dlrn.")
    parser.add_argument('--use-public', action="store_true",
                        help="Use the public master repo for dependencies "
                             "when doing install verification.")
    parser.add_argument('--order', action="store_true",
                        help="Compute the build order according to the spec "
                             "files instead of the dates of the commits. "
                             "Implies --sequential.")
    parser.add_argument('--sequential', action="store_true",
                        help="Run all actions sequentially, regardless of the"
                             " number of workers specified in projects.ini.")
    parser.add_argument('--status', action="store_true",
                        help="Get the status of packages.")
    parser.add_argument('--recheck', action="store_true",
                        help="Force a rebuild for a particular package. "
                        "Implies --package-name")
    parser.add_argument('--force-recheck', action="store_true",
                        help="Force a rebuild for a particular package, even "
                        "if its last build was successful. Requires setting "
                        "allow_force_rechecks=True in projects.ini. "
                        "Implies --package-name and --recheck")
    parser.add_argument('--version',
                        action='version',
                        version=version.version_info.version_string())
    parser.add_argument('--run',
                        help="Run a program instead of trying to build. "
                             "Implies --head-only")
    parser.add_argument('--stop', action="store_true",
                        help="Stop on error.")
    parser.add_argument('--verbose-build', action="store_true",
                        help="Show verbose output during the package build.")
    parser.add_argument('--verbose-mock', action="store_true",
                        help=argparse.SUPPRESS)
    parser.add_argument('--no-repo', action="store_true",
                        help="Do not generate a repo with all the built "
                        "packages.")
    parser.add_argument('--debug', action='store_true',
                        help="Print debug logs")

    options = parser.parse_args(sys.argv[1:])

    setup_logging(options.debug)

    if options.verbose_mock:
        logger.warning('The --verbose-mock command-line option is deprecated.'
                       ' Please use --verbose-build instead.')
        options.verbose_build = options.verbose_mock
    global verbose_build
    verbose_build = options.verbose_build

    cp = configparser.RawConfigParser()
    cp.read(options.config_file)

    if options.log_commands is True:
        logging.getLogger("sh.command").setLevel(logging.INFO)
    if options.order is True:
        options.sequential = True

    config_options = ConfigOptions(cp, overrides=options.config_override)
    if options.dev:
        _, tmpdb_path = tempfile.mkstemp()
        logger.info("Using file %s for temporary db" % tmpdb_path)
        config_options.database_connection = "sqlite:///%s" % tmpdb_path

    session = getSession(config_options.database_connection)
    pkginfo_driver = config_options.pkginfo_driver
    global pkginfo
    pkginfo = import_object(pkginfo_driver, cfg_options=config_options)
    packages = pkginfo.getpackages(local_info_repo=options.info_repo,
                                   tags=config_options.tags,
                                   dev_mode=options.dev)

    if options.project_name:
        pkg_names = [p['name'] for p in packages
                     if p['project'] in options.project_name]
    elif options.package_name:
        pkg_names = options.package_name
    else:
        pkg_names = None

    if options.status is True:
        if not pkg_names:
            pkg_names = [p['name'] for p in packages]
        for name in pkg_names:
            package = [p for p in packages if p['name'] == name][0]
            for build_type in package.get('types', ['rpm']):
                commit = getLastProcessedCommit(
                    session, name, 'invalid status',
                    type=build_type)
                if commit:
                    print("{:>9}".format(build_type), name, commit.status)
                else:
                    print("{:>9}".format(build_type), name, 'NO_BUILD')
        sys.exit(0)

    if pkg_names:
        pkg_name = pkg_names[0]
    else:
        pkg_name = None

    def recheck_commit(commit, force):
        if commit.status == 'SUCCESS':
            if not force:
                logger.error(
                    "Trying to recheck an already successful commit,"
                    " ignoring. If you want to force it, use --force-recheck"
                    " and set allow_force_rechecks=True in projects.ini")
                sys.exit(1)
            else:
                logger.info("Forcefully rechecking a successfully built "
                            "commit for %s" % commit.project_name)
        elif commit.status == 'RETRY':
            # In this case, we are going to retry anyway, so
            # do nothing and exit
            logger.warning("Trying to recheck a commit in RETRY state,"
                           " ignoring.")
            sys.exit(0)
        # We could set the status to RETRY here, but if we have gone
        # beyond max_retries it wouldn't work as expected. Thus, our
        # only chance is to remove the commit
        session.delete(commit)
        session.commit()
        sys.exit(0)

    if options.recheck is True:
        if not pkg_name:
            logger.error('Please use --package-name or --project-name '
                         'with --recheck.')
            sys.exit(1)

        if options.force_recheck and config_options.allow_force_rechecks:
            force_recheck = True
        else:
            force_recheck = False
        package = [p for p in packages if p['name'] == pkg_name][0]
        for build_type in package.get('types', ['rpm']):
            commit = getLastProcessedCommit(session, pkg_name, type=build_type)
            if commit:
                recheck_commit(commit, force_recheck)
            else:
                logger.error("There are no existing commits for package %s",
                             pkg_name)
                sys.exit(1)
    # when we run a program instead of building we don't care about
    # the commits, we just want to run once per package
    if options.run:
        options.head_only = True
    # Build a list of commits we need to process
    toprocess = []
    skipped_list = []

    if not pkg_name and not pkg_names:
        pool = multiprocessing.Pool()   # This will use all the system cpus
        # Use functools.partial to iterate on the packages to process,
        # while keeping a few options fixed
        getinfo_wrapper = partial(getinfo, local=options.local,
                                  dev_mode=options.dev,
                                  head_only=options.head_only,
                                  db_connection=config_options.
                                  database_connection)
        iterator = pool.imap(getinfo_wrapper, packages)
        while True:
            try:
                project_toprocess, updated_pkg, skipped = iterator.next()
                for package in packages:
                    if package['name'] == updated_pkg['name']:
                        if package['upstream'] == 'Unknown':
                            package['upstream'] = updated_pkg['upstream']
                            logger.debug(
                                "Updated upstream for package %s to %s",
                                package['name'], package['upstream'])
                        break
                if skipped:
                    skipped_list.append(updated_pkg['name'])
                _add_commits(project_toprocess, toprocess, options, session)
            except StopIteration:
                break
        pool.close()
        pool.join()
    else:
        for package in packages:
            if package['name'] in pkg_names:
                project_toprocess, _, skipped = getinfo(
                    package, local=options.local,
                    dev_mode=options.dev,
                    head_only=options.head_only,
                    db_connection=config_options.
                    database_connection)
                if skipped:
                    skipped_list.append(package['name'])
                _add_commits(project_toprocess, toprocess, options, session)
    closeSession(session)   # Close session, will reopen during post_build

    # Store skip list
    datadir = os.path.realpath(config_options.datadir)
    if not os.path.exists(os.path.join(datadir, 'repos')):
        os.makedirs(os.path.join(datadir, 'repos'))
    with open(os.path.join(datadir, 'repos', 'skiplist.txt'), 'w') as fp:
        for pkg in skipped_list:
            fp.write(pkg + '\n')

    # Check if there is any commit at all to process
    if len(toprocess) == 0:
        if not pkg_name:
            # Use a shorter message if this was a full run
            logger.info("No commits to build.")
        else:
            logger.info("No commits to build. If this is not expected, please"
                        " make sure the package name(s) are correct, and that "
                        "any failed commit you want to rebuild has been "
                        "removed from the database.")
        return 0

    # if requested do a sort according to build and install
    # dependencies
    if options.order is True:
        # collect info from all spec files
        logger.info("Reading rpm spec files")
        projects = sorted([c.project_name for c in toprocess])

        speclist = []
        bootstraplist = []
        for project_name in projects:
            # Preprocess spec if needed
            pkginfo.preprocess(package_name=project_name)

            filename = None
            for f in os.listdir(pkginfo.distgit_dir(project_name)):
                if f.endswith('.spec'):
                    filename = f

            if filename:
                specpath = os.path.join(pkginfo.distgit_dir(project_name),
                                        filename)
                speclist.append(sh.rpmspec('-D', 'repo_bootstrap 1',
                                           '-P', specpath))
                # Check if repo_bootstrap is defined in the package.
                # If so, we'll need to rebuild after the whole bootstrap
                rawspec = open(specpath).read(-1)
                if 'repo_bootstrap' in rawspec:
                    bootstraplist.append(project_name)
            else:
                logger.warning("Could not find a spec for package %s" %
                               project_name)

        logger.debug("Packages to rebuild: %s" % bootstraplist)

        specs = RpmSpecCollection([RpmSpecFile(spec)
                                  for spec in speclist])
        # compute order according to BuildRequires
        logger.info("Computing build order")
        orders = specs.compute_order()
        # hack because the package name is not consistent with the directory
        # name and the spec file name
        if 'python-networking_arista' in orders:
            orders.insert(orders.index('python-networking_arista'),
                          'python-networking-arista')

        # sort the commits according to the score of their project and
        # then use the timestamp of the commits as a secondary key
        def my_cmp(a, b):
            if a.project_name == b.project_name:
                _a = a.dt_commit
                _b = b.dt_commit
            else:
                _a = orders.index(a.project_name) if a.project_name in \
                    orders else sys.maxsize
                _b = orders.index(b.project_name) if b.project_name in \
                    orders else sys.maxsize
            # cmp is no longer available in python3 so replace it. See Ordering
            # Comparisons on:
            # https://docs.python.org/3.0/whatsnew/3.0.html
            return (_a > _b) - (_a < _b)

        toprocess.sort(key=cmp_to_key(my_cmp))
    else:
        # sort according to the timestamp of the commits
        toprocess.sort()

    exit_code = 0
    if options.sequential is True:
        toprocess_copy = deepcopy(toprocess)
        for commit in toprocess:
            status = build_worker(packages, commit, run_cmd=options.run,
                                  build_env=options.build_env,
                                  dev_mode=options.dev,
                                  use_public=options.use_public,
                                  order=options.order, sequential=True)
            exception = status[3]
            consistent = False
            datadir = os.path.realpath(config_options.datadir)
            with lock_file(os.path.join(datadir, 'remote.lck')):
                session = getSession(config_options.database_connection)
                if exception is not None:
                    logger.error("Received exception %s" % exception)
                    failures = 1
                else:
                    if not options.run:
                        failures = post_build(status, packages, session,
                                              build_repo=not options.no_repo)
                        consistent = (failures == 0)
                exit_value = process_build_result(status, packages, session,
                                                  toprocess_copy,
                                                  dev_mode=options.dev,
                                                  run_cmd=options.run,
                                                  stop=options.stop,
                                                  build_env=options.build_env,
                                                  head_only=options.head_only,
                                                  consistent=consistent,
                                                  failures=failures)
                closeSession(session)

            if exit_value != 0:
                exit_code = exit_value
            if options.stop and exit_code != 0:
                return exit_code
    else:
        # Setup multiprocessing pool
        pool = multiprocessing.Pool(config_options.workers)
        # Use functools.partial to iterate on the commits to process,
        # while keeping a few options fixed
        build_worker_wrapper = partial(build_worker, packages,
                                       run_cmd=options.run,
                                       build_env=options.build_env,
                                       dev_mode=options.dev,
                                       use_public=options.use_public,
                                       order=options.order, sequential=False)
        iterator = pool.imap(build_worker_wrapper, toprocess)

        while True:
            try:
                status = iterator.next()
                exception = status[3]
                consistent = False
                datadir = os.path.realpath(config_options.datadir)
                with lock_file(os.path.join(datadir, 'remote.lck')):
                    session = getSession(config_options.database_connection)
                    if exception is not None:
                        logger.info("Received exception %s" % exception)
                        failures = 1
                    else:
                        # Create repo, build versions.csv file.
                        # This needs to be sequential
                        if not options.run:
                            failures = post_build(
                                status, packages, session,
                                build_repo=not options.no_repo)
                            consistent = (failures == 0)
                    exit_value = process_build_result(
                        status, packages,
                        session, toprocess,
                        dev_mode=options.dev,
                        run_cmd=options.run,
                        stop=options.stop,
                        build_env=options.build_env,
                        head_only=options.head_only,
                        consistent=consistent,
                        failures=failures)
                    closeSession(session)
                if exit_value != 0:
                    exit_code = exit_value
                if options.stop and exit_code != 0:
                    return exit_code
            except StopIteration:
                break
        pool.close()
        pool.join()

    # If we were bootstrapping, set the packages that required it to RETRY
    session = getSession(config_options.database_connection)
    if options.order is True and not pkg_name:
        for bpackage in bootstraplist:
            commit = getLastProcessedCommit(session, bpackage)
            commit.status = 'RETRY'
            session.add(commit)
            session.commit()
    genreports(packages, options.head_only, session, [])
    closeSession(session)

    if options.dev:
        os.remove(tmpdb_path)
    return exit_code


def process_build_result(status, *args, **kwargs):
    if status[0].type == "rpm":
        return process_build_result_rpm(status, *args, **kwargs)
    elif status[0].type == "container":
        return process_build_result_container(status, *args, **kwargs)
    else:
        raise Exception("Unknown type %s" % status[0].type)


def process_build_result_container(
        status, packages, session, packages_to_process,
        dev_mode=False, run_cmd=False, stop=False,
        build_env=None, head_only=False, consistent=False,
        failures=0):
    raise NotImplementedError()


def process_build_result_rpm(
        status, packages, session, packages_to_process,
        dev_mode=False, run_cmd=False, stop=False,
        build_env=None, head_only=False, consistent=False,
        failures=0):
    config_options = getConfigOptions()
    commit = status[0]
    built_rpms = status[1]
    notes = status[2]
    exception = status[3]
    commit_hash = commit.commit_hash
    project = commit.project_name
    project_info = session.query(Project).filter(
        Project.project_name == project).first()
    if not project_info:
        project_info = Project(project_name=project, last_email=0)
    exit_code = 0

    if run_cmd:
        if exception is not None:
            exit_code = 1
            if stop:
                return exit_code
        return exit_code

    if exception is None:
        commit.status = "SUCCESS"
        commit.notes = notes
        commit.artifacts = ",".join(built_rpms)
    else:
        logger.error("Received exception %s" % exception)

        datadir = os.path.realpath(config_options.datadir)
        yumrepodir = os.path.join(datadir, "repos",
                                  commit.getshardedcommitdir())
        logfile = os.path.join(yumrepodir,
                               "rpmbuild.log")

        # If the log file hasn't been created we add what we have
        # This happens if the rpm build script didn't run.
        if not os.path.exists(yumrepodir):
            os.makedirs(yumrepodir)
        if not os.path.exists(logfile):
            with open(logfile, "w") as fp:
                fp.write(str(exception))

        if (isknownerror(logfile) and
            (timesretried(project, session, commit_hash, commit.distro_hash) <
             config_options.maxretries)):
            logger.exception("Known error building packages for %s,"
                             " will retry later" % project)
            commit.status = "RETRY"
            commit.notes = str(exception)
            # do not switch from an error exit code to a retry
            # exit code
            if exit_code != 1:
                exit_code = 2
        else:
            exit_code = 1

            if not project_info.suppress_email():
                sendnotifymail(packages, commit)
                project_info.sent_email()
                session.add(project_info)

            # allow to submit a gerrit review only if the last build
            # was successful or non existent to avoid creating a gerrit
            # review for the same problem multiple times.
            if config_options.gerrit is not None:
                if build_env:
                    env_vars = list(build_env)
                else:
                    env_vars = []
                last_build = getLastProcessedCommit(session, project)
                if not last_build or last_build.status == 'SUCCESS':
                    try:
                        submit_review(commit, packages, env_vars)
                    except Exception:
                        logger.error('Unable to create review '
                                     'see review.log')
                else:
                    logger.info('Last build not successful '
                                'for %s' % project)
            commit.status = "FAILED"
            commit.notes = str(exception)
        if stop:
            return exit_code
    # Add commit to the session
    session.add(commit)

    genreports(packages, head_only, session, packages_to_process)
    # Export YAML file containing commit metadata
    export_commit_yaml(commit)
    try:
        sync_repo(commit)
    except Exception as e:
        logger.error('Repo sync failed for project %s' % project)
        consistent = False  # If we were consistent before, we are not anymore
        if exit_code == 0:  # The commit was ok, so marking as failed
            exit_code = 1
            # We need to make the commit status be "failed"
            commit.status = "FAILED"
            commit.notes = str(e)
            session.add(commit)
            # And open a review if needed
            if config_options.gerrit is not None:
                if build_env:
                    env_vars = list(build_env)
                else:
                    env_vars = []
                try:
                    submit_review(commit, packages, env_vars)
                except Exception:
                    logger.error('Unable to create review '
                                 'see review.log')

    session.commit()

    # Generate the current and consistent symlinks
    if exception is None:
        dirnames = ['current']
        datadir = os.path.realpath(config_options.datadir)
        yumrepodir = os.path.join(datadir, "repos",
                                  commit.getshardedcommitdir())
        yumrepodir_abs = os.path.join(datadir, yumrepodir)
        if consistent:
            dirnames.append('consistent')
        else:
            if config_options.use_components:
                logger.info('%d packages not built correctly for component'
                            ' %s: not updating the consistent symlink' %
                            (failures, commit.component))
            else:
                logger.info('%d packages not built correctly: not updating'
                            ' the consistent symlink' % failures)
        for dirname in dirnames:
            if config_options.use_components:
                target_repo_dir = os.path.join(datadir, "repos/component",
                                               commit.component, dirname)
                source_repo_dir = os.path.join(datadir, "repos/component",
                                               commit.component)
            else:
                target_repo_dir = os.path.join(datadir, "repos", dirname)
                source_repo_dir = os.path.join(datadir, "repos")
            os.symlink(os.path.relpath(yumrepodir_abs, source_repo_dir),
                       target_repo_dir + "_")
            os.rename(target_repo_dir + "_", target_repo_dir)

        # If using components, synchronize the upper-level repo files
        if config_options.use_components:
            for dirname in dirnames:
                aggregate_repo_files(dirname, datadir, session,
                                     config_options.reponame, hashed_dir=True)

        # And synchronize them
        sync_symlinks(commit)

    if dev_mode is False:
        if consistent:
            # We have a consistent repo. Let's create a CIVote entry in the DB
            vote = CIVote(commit_id=commit.id, ci_name='consistent',
                          ci_url='', ci_vote=True, ci_in_progress=False,
                          timestamp=int(commit.dt_build), notes='',
                          component=commit.component)
            session.add(vote)
            session.commit()
    return exit_code


def export_commit_yaml(commit):
    config_options = getConfigOptions()
    # Export YAML file containing commit metadata
    datadir = os.path.realpath(config_options.datadir)
    yumrepodir = os.path.join(datadir, "repos",
                              commit.getshardedcommitdir())
    saveYAML_commit(commit, os.path.join(yumrepodir, 'commit.yaml'))


def post_build(status, *args, **kwargs):
    if status[0].type == "rpm":
        return post_build_rpm(status, *args, **kwargs)
    elif status[0].type == "container":
        return post_build_container(status, *args, **kwargs)
    else:
        raise Exception("Unknown type %s" % status[0].type)


def post_build_container(status, packages, session, build_repo=None):
    raise NotImplementedError()


def post_build_rpm(status, packages, session, build_repo=True):
    config_options = getConfigOptions()
    commit = status[0]
    built_rpms = status[1]
    project_name = commit.project_name
    commit_hash = commit.commit_hash
    datadir = os.path.realpath(config_options.datadir)
    yumrepodir = os.path.join("repos", commit.getshardedcommitdir())
    yumrepodir_abs = os.path.join(datadir, yumrepodir)

    shafile = open(os.path.join(yumrepodir_abs, "versions.csv"), "w")
    shafile.write("Project,Source Repo,Source Sha,Dist Repo,Dist Sha,"
                  "Status,Last Success Timestamp,Component,Extended Sha,"
                  "Pkg NVR\n")
    failures = 0

    for otherproject in packages:
        if (config_options.use_components and 'component' in otherproject and
                otherproject['component'] != commit.component):
            # Only dump information and create symlinks for the same component
            continue

        otherprojectname = otherproject["name"]
        if otherprojectname == project_name:
            # Output sha's this project
            dumpshas2file(shafile, commit, otherproject["upstream"],
                          otherproject["master-distgit"], "SUCCESS",
                          commit.dt_build, commit.component, built_rpms)
            continue
        # Output sha's of all other projects represented in this repo
        last_success = getCommits(session, project=otherprojectname,
                                  with_status="SUCCESS",
                                  type=commit.type).first()
        last_processed = getCommits(session, project=otherprojectname,
                                    type=commit.type).first()

        if last_success:
            if build_repo:
                for rpm in last_success.artifacts.split(","):
                    rpm_link_src = os.path.join(yumrepodir_abs,
                                                os.path.split(rpm)[1])
                    os.symlink(os.path.relpath(os.path.join(datadir, rpm),
                                               yumrepodir_abs), rpm_link_src)
            last = last_success
        else:
            last = last_processed
        if last:
            if last.artifacts:
                rpmlist = last.artifacts.split(",")
            else:
                rpmlist = []
            upstream = otherproject.get('upstream', '')
            dumpshas2file(shafile, last, upstream,
                          otherproject["master-distgit"],
                          last_processed.status, last.dt_build,
                          commit.component, rpmlist)
            if last_processed.status != 'SUCCESS':
                failures += 1
        else:
            failures += 1
    shafile.close()

    if build_repo:
        # Use createrepo_c when available
        try:
            from sh import createrepo_c
            sh.createrepo = createrepo_c
        except ImportError:
            pass

        if config_options.include_srpm_in_repo:
            sh.createrepo(yumrepodir_abs)
        else:
            sh.createrepo('-x', '*.src.rpm', yumrepodir_abs)

        with open(os.path.join(
                yumrepodir_abs, "%s.repo" % config_options.reponame),
                "w") as fp:
            if config_options.use_components:
                repo_id = "%s-component-%s" % (config_options.reponame,
                                               commit.component)
            else:
                repo_id = config_options.reponame
            fp.write("[%s]\nname=%s-%s-%s\nbaseurl=%s/%s\nenabled=1\n"
                     "gpgcheck=0\npriority=1\n" % (
                         repo_id,
                         config_options.reponame,
                         project_name, commit_hash,
                         config_options.baseurl,
                         commit.getshardedcommitdir()))

    return failures


def getinfo(package, local=False, dev_mode=False, head_only=False,
            db_connection=None, type="rpm"):
    project = package["name"]
    since = "-1"
    session = getSession(db_connection)
    commit = getLastProcessedCommit(session, project, type=type)
    if commit:
        # If we have switched source branches, we want to behave
        # as if no previous commits had been built, and only build
        # the last one
        if commit.commit_branch == getsourcebranch(package):
            # This will return all commits since the last handled commit
            # including the last handled commit, remove it later if needed.
            since = "--after=%d" % (commit.dt_commit)
        else:
            # The last processed commit belongs to a different branch. Just
            # in case, let's check if we built a previous commit from the
            # current branch
            commit = getLastBuiltCommit(session, project,
                                        getsourcebranch(package), type=type)
            if commit:
                logger.info("Last commit belongs to another branch, but"
                            " we're ok with that")
                since = "--after=%d" % (commit.dt_commit)
                # In any case, we just want to build the last commit, if any
                head_only = True

    project_toprocess, skipped = pkginfo.getinfo(
        project=project, package=package,
        since=since, local=local,
        dev_mode=dev_mode, type=type)

    closeSession(session)
    # If since == -1, then we only want to trigger a build for the
    # most recent change
    if since == "-1" or head_only:
        del project_toprocess[:-1]

    return project_toprocess, package, skipped
