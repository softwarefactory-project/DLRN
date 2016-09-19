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

from functools import partial

from prettytable import PrettyTable
import sh
from six.moves import configparser

from dlrn.build import build_worker

from dlrn.config import ConfigOptions
from dlrn.config import getConfigOptions

from dlrn.db import Commit
from dlrn.db import getCommits
from dlrn.db import getLastBuiltCommit
from dlrn.db import getLastProcessedCommit
from dlrn.db import getSession
from dlrn.db import Project
from dlrn.notifications import sendnotifymail
from dlrn.notifications import submit_review
from dlrn.reporting import genreports
from dlrn.reporting import get_commit_url
from dlrn.repositories import getsourcebranch
from dlrn.rpmspecfile import RpmSpecCollection
from dlrn.rpmspecfile import RpmSpecFile
from dlrn.rsync import sync_repo
from dlrn.utils import dumpshas2file
from dlrn.utils import import_object
from dlrn.utils import isknownerror
from dlrn.utils import saveYAML_commit
from dlrn.utils import timesretried
from dlrn import version

logging.basicConfig(level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("dlrn")
logger.setLevel(logging.INFO)

default_options = {'maxretries': '3', 'tags': None, 'gerrit': None,
                   'templatedir': os.path.join(
                       os.path.dirname(os.path.realpath(__file__)),
                       "templates"),
                   'rsyncdest': '', 'rsyncport': '22',
                   'pkginfo_driver': 'dlrn.drivers.rdoinfo.RdoInfoDriver',
                   'workers': '1',
                   'gerrit_topic': 'rdo-FTBFS',
                   }


def main():
    parser = argparse.ArgumentParser()
    # Some of the non-positional arguments are required, so change the text
    # saying "optional arguments" to just "arguments":
    parser._optionals.title = 'arguments'

    parser.add_argument('--config-file',
                        help="Config file (required).",
                        required=True)
    parser.add_argument('--info-repo',
                        help="use a local rdoinfo repo instead of "
                             "fetching the default one using rdopkg. Only"
                             "applies when pkginfo_driver is rdoinfo in"
                             "projects.ini")
    parser.add_argument('--build-env', action='append',
                        help="Variables for the build environment.")
    parser.add_argument('--local', action="store_true",
                        help="Use local git repos if possible.")
    parser.add_argument('--head-only', action="store_true",
                        help="Build from the most recent Git commit only.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--project-name', action='append',
                       help="Build a specific project name only."
                            "Use multiple times to build more than one "
                            "project in a run.")
    group.add_argument('--package-name', action='append',
                       help="Build a specific package name only."
                            "Use multiple times to build more than one "
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
                        "Imply --package-name")
    parser.add_argument('--version',
                        action='version',
                        version=version.version_info.version_string())
    parser.add_argument('--run',
                        help="Run a program instead of trying to build. "
                             "Imply --head-only")
    parser.add_argument('--stop', action="store_true",
                        help="Stop on error.")
    parser.add_argument('--verbose-mock', action="store_true",
                        help="Show verbose mock output during build.")

    options, args = parser.parse_known_args(sys.argv[1:])

    global verbose_mock
    verbose_mock = options.verbose_mock

    cp = configparser.RawConfigParser(default_options)
    cp.read(options.config_file)

    if options.log_commands is True:
        logging.getLogger("sh.command").setLevel(logging.INFO)
    if options.order is True:
        options.sequential = True

    session = getSession('sqlite:///commits.sqlite')
    config_options = ConfigOptions(cp)
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
            commit = getLastProcessedCommit(session, name, 'invalid status')
            if commit:
                print(name, commit.status)
            else:
                print(name, 'NO_BUILD')
        sys.exit(0)

    if pkg_names:
        pkg_name = pkg_names[0]
    else:
        pkg_name = None

    if options.recheck is True:
        if not pkg_name:
            logger.error('Please use --package-name or --project-name '
                         'with --recheck.')
            sys.exit(1)
        commit = getLastProcessedCommit(session, pkg_name)
        if commit:
            if commit.status == 'SUCCESS':
                logger.error("Trying to recheck an already successful commit,"
                             " ignoring.")
                sys.exit(1)
            elif commit.status == 'RETRY':
                # In this case, we are going to retry anyway, so
                # do nothing and exit
                logger.warning("Trying to recheck a commit in RETRY state,"
                               " ignoring.")
                sys.exit(0)
            else:
                # We could set the status to RETRY here, but if we have gone
                # beyond max_retries it wouldn't work as expected. Thus, our
                # only chance is to remove the commit
                session.delete(commit)
                session.commit()
                sys.exit(0)
        else:
                logger.error("There are no existing commits for package %s"
                             % pkg_name)
                sys.exit(1)
    # when we run a program instead of building we don't care about
    # the commits, we just want to run once per package
    if options.run:
        options.head_only = True
    # Build a list of commits we need to process
    toprocess = []
    for package in packages:
        project = package["name"]
        since = "-1"
        commit = getLastProcessedCommit(session, project)
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
                                            getsourcebranch(package))
                if commit:
                    logger.info("Last commit belongs to another branch, but"
                                " we're ok with that")
                    since = "--after=%d" % (commit.dt_commit)

        if not pkg_name or package["name"] in pkg_names:
            project_toprocess = pkginfo.getinfo(project=project,
                                                package=package,
                                                since=since,
                                                local=options.local,
                                                dev_mode=options.dev)
            # If since == -1, then we only want to trigger a build for the
            # most recent change
            if since == "-1" or options.head_only:
                del project_toprocess[:-1]

            # The first entry in the list of commits is a commit we have
            # already processed, we want to process it again only if in dev
            # mode or distro hash has changed, we can't simply check against
            # the last commit in the db, as multiple commits can have the same
            # commit date
            for commit_toprocess in project_toprocess:
                if ((options.dev is True) or
                    options.run or
                    (not session.query(Commit).filter(
                        Commit.commit_hash == commit_toprocess.commit_hash,
                        Commit.distro_hash == commit_toprocess.distro_hash,
                        Commit.status != "RETRY")
                        .all())):
                    toprocess.append(commit_toprocess)

    # if requested do a sort according to build and install
    # dependencies
    if options.order is True and not pkg_name:
        # collect info from all spec files
        logger.info("Reading rpm spec files")
        projects = sorted([p['name'] for p in packages])

        speclist = []
        bootstraplist = []
        for project_name in projects:
            # Preprocess spec if needed
            pkginfo.preprocess(package_name=project_name)

            specpath = os.path.join(pkginfo.distgit_dir(project_name),
                                    project_name + '.spec')
            speclist.append(sh.rpmspec('-D', 'repo_bootstrap 1',
                                       '-P', specpath))

            # Check if repo_bootstrap is defined in the package.
            # If so, we'll need to rebuild after the whole bootstrap exercise
            rawspec = open(specpath).read(-1)
            if 'repo_bootstrap' in rawspec:
                bootstraplist.append(project_name)

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
                return cmp(a.dt_commit, b.dt_commit)
            return cmp(orders.index(a.project_name),
                       orders.index(b.project_name))
        toprocess.sort(cmp=my_cmp)
    else:
        # sort according to the timestamp of the commits
        toprocess.sort()

    exit_code = 0
    if options.sequential is True:
        for commit in toprocess:
            status = build_worker(packages, commit, run_cmd=options.run,
                                  build_env=options.build_env,
                                  dev_mode=options.dev,
                                  use_public=options.use_public,
                                  order=options.order, sequential=True)
            exception = status[3]
            if exception is not None:
                logger.error("Received exception %s" % exception)
            else:
                if not options.run:
                    post_build(status, packages, session)
            exit_value = process_build_result(status, packages, session,
                                              dev_mode=options.dev,
                                              run_cmd=options.run,
                                              stop=options.stop,
                                              build_env=options.build_env,
                                              head_only=options.head_only)
            if exit_value != 0:
                exit_code = exit_value

            # Export YAML file containing commit metadata
            export_commit_yaml(status[0])
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
                if exception is not None:
                    logger.info("Received exception %s" % exception)
                else:
                    # Create repo, build versions.csv file.
                    # This needs to be sequential
                    if not options.run:
                        post_build(status, packages, session)
                exit_value = process_build_result(status, packages,
                                                  session,
                                                  dev_mode=options.dev,
                                                  run_cmd=options.run,
                                                  stop=options.stop,
                                                  build_env=options.build_env,
                                                  head_only=options.head_only)
                if exit_value != 0:
                    exit_code = exit_value

                # Export YAML file containing commit metadata
                export_commit_yaml(status[0])
                if options.stop and exit_code != 0:
                    return exit_code
            except StopIteration:
                break

    # If we were bootstrapping, set the packages that required it to RETRY
    if options.order is True and not pkg_name:
        for bpackage in bootstraplist:
            commit = getLastProcessedCommit(session, bpackage)
            commit.status = 'RETRY'
            session.add(commit)
            session.commit()
    genreports(packages, options.head_only)
    return exit_code


def process_build_result(status, packages, session, dev_mode=False,
                         run_cmd=False, stop=False, build_env=None,
                         head_only=False):
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

    if exception is not None:
        logger.error("Received exception %s" % exception)

        datadir = os.path.realpath(config_options.datadir)
        yumrepodir = os.path.join(datadir, "repos",
                                  commit.getshardedcommitdir())
        logfile = os.path.join(yumrepodir,
                               "rpmbuild.log")
        if (isknownerror(logfile) and
            (timesretried(project, session, commit_hash, commit.distro_hash) <
             config_options.maxretries)):
            logger.exception("Known error building packages for %s,"
                             " will retry later" % project)
            commit.status = "RETRY"
            commit.notes = getattr(exception, "message", notes)
            session.add(commit)
            # do not switch from an error exit code to a retry
            # exit code
            if exit_code != 1:
                exit_code = 2
        else:
            exit_code = 1
            # If the log file hasn't been created we add what we have
            # This happens if the rpm build script didn't run.
            if not os.path.exists(yumrepodir):
                os.makedirs(yumrepodir)
            if not os.path.exists(logfile):
                with open(logfile, "w") as fp:
                    fp.write(getattr(exception, "message", notes))

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
                    for pkg in packages:
                        if project == pkg['name']:
                            break
                    else:
                        pkg = None
                    if pkg:
                        url = (get_commit_url(commit, pkg) +
                               commit.commit_hash)
                        env_vars.append('GERRIT_URL=%s' % url)
                        env_vars.append('GERRIT_LOG=%s/%s' %
                                        (config_options.baseurl,
                                         commit.getshardedcommitdir()))
                        maintainers = ','.join(pkg['maintainers'])
                        env_vars.append('GERRIT_MAINTAINERS=%s' %
                                        maintainers)
                        env_vars.append('GERRIT_TOPIC=%s' %
                                        config_options.gerrit_topic)
                        logger.info('Creating a gerrit review using '
                                    'GERRIT_URL=%s '
                                    'GERRIT_MAINTAINERS=%s ' %
                                    (url, maintainers))
                        try:
                            submit_review(commit, env_vars)
                        except Exception:
                            logger.error('Unable to create review '
                                         'see review.log')
                    else:
                        logger.error('Unable to find info for project'
                                     ' %s' % project)
                else:
                    logger.info('Last build not successful '
                                'for %s' % project)
            commit.status = "FAILED"
            commit.notes = getattr(exception, "message", notes)
            session.add(commit)
        if stop:
            return exit_code
    else:
        commit.status = "SUCCESS"
        commit.notes = notes
        commit.rpms = ",".join(built_rpms)
        session.add(commit)
    if dev_mode is False:
        session.commit()
    genreports(packages, head_only)
    # TODO(jpena): could we launch this asynchronously?
    sync_repo(commit)
    return exit_code


def compare():
    parser = argparse.ArgumentParser()
    parser.add_argument('--info-repo',
                        help="use a local rdoinfo repo instead of "
                             "fetching the default one using rdopkg. Only"
                             "applies when pkginfo_driver is rdoinfo in"
                             "projects.ini")
    config_options = getConfigOptions()
    options, args = parser.parse_known_args(sys.argv[1:])
    pkginfo_driver = config_options.pkginfo_driver
    pkginfo_object = import_object(pkginfo_driver, cfg_options=config_options)
    packages = pkginfo_object.getpackages(local_info_repo=options.info_repo,
                                          tags=config_options.tags)

    compare_details = {}
    # Each argument is a ":" seperate filename:title, this filename is the
    # sqlite db file and the title is whats used in the dable being displayed
    table_header = ["Name", "Out of Sync"]
    for dbdetail in args:
        dbfilename, dbtitle = dbdetail.split(":")
        table_header.extend((dbtitle + " upstream", dbtitle + " spec"))

        session = getSession('sqlite:///%s' % dbfilename)

        for package in packages:
            package_name = package["name"]
            compare_details.setdefault(package_name, [package_name, " "])
            last_success = getCommits(session, project=package_name,
                                      with_status="SUCCESS").first()
            if last_success:
                compare_details[package_name].extend(
                    (last_success.commit_hash[:8],
                     last_success.distro_hash[:8]))
            else:
                compare_details[package_name].extend(("None", "None"))
        session.close()

    table = PrettyTable(table_header)
    for name, compare_detail in compare_details.items():
        if len(set(compare_detail)) > 4:
            compare_detail[1] = "*"
        table.add_row(compare_detail)
    print(table)


def export_commit_yaml(commit):
    config_options = getConfigOptions()
    # Export YAML file containing commit metadata
    datadir = os.path.realpath(config_options.datadir)
    yumrepodir = os.path.join(datadir, "repos",
                              commit.getshardedcommitdir())
    saveYAML_commit(commit, os.path.join(yumrepodir, 'commit.yaml'))


def post_build(status, packages, session):
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
                  "Status,Last Success Timestamp,Pkg NVR\n")
    failures = 0

    for otherproject in packages:
        otherprojectname = otherproject["name"]
        if otherprojectname == project_name:
            # Output sha's this project
            dumpshas2file(shafile, commit, otherproject["upstream"],
                          otherproject["master-distgit"], "SUCCESS",
                          commit.dt_build, built_rpms)
            continue
        # Output sha's of all other projects represented in this repo
        last_success = getCommits(session, project=otherprojectname,
                                  with_status="SUCCESS").first()
        last_processed = getLastProcessedCommit(session, otherprojectname,
                                                'INVALID STATE')
        if last_success:
            for rpm in last_success.rpms.split(","):
                rpm_link_src = os.path.join(yumrepodir_abs,
                                            os.path.split(rpm)[1])
                os.symlink(os.path.relpath(os.path.join(datadir, rpm),
                                           yumrepodir_abs), rpm_link_src)
            last = last_success
        else:
            last = last_processed
        if last:
            if last.rpms:
                rpmlist = last.rpms.split(",")
            else:
                rpmlist = []
            dumpshas2file(shafile, last, otherproject["upstream"],
                          otherproject["master-distgit"],
                          last_processed.status, last.dt_build,
                          rpmlist)
            if last_processed.status != 'SUCCESS':
                failures += 1
        else:
            failures += 1
    shafile.close()

    # Use createrepo_c when available
    try:
        from sh import createrepo_c
        sh.createrepo = createrepo_c
    except ImportError:
        pass
    sh.createrepo(yumrepodir_abs)

    with open(os.path.join(
            yumrepodir_abs, "%s.repo" % config_options.reponame),
            "w") as fp:
        fp.write("[%s]\nname=%s-%s-%s\nbaseurl=%s/%s\nenabled=1\n"
                 "gpgcheck=0\npriority=1" % (config_options.reponame,
                                             config_options.reponame,
                                             project_name, commit_hash,
                                             config_options.baseurl,
                                             commit.getshardedcommitdir()))

    dirnames = ['current']

    if failures == 0:
        dirnames.append('consistent')
    else:
        logger.info('%d packages not built correctly: not updating'
                    ' the consistent symlink' % failures)
    for dirname in dirnames:
        target_repo_dir = os.path.join(datadir, "repos", dirname)
        os.symlink(os.path.relpath(yumrepodir_abs,
                                   os.path.join(datadir, "repos")),
                   target_repo_dir + "_")
        os.rename(target_repo_dir + "_", target_repo_dir)
