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
import copy
import filecmp
import logging
import multiprocessing
import os
import re
import shutil
import smtplib
import sys
import urllib2

from time import time

from email.mime.text import MIMEText
from pbr.version import SemanticVersion

from prettytable import PrettyTable
import sh
from six.moves import configparser


from dlrn.config import ConfigOptions

from dlrn.db import Commit
from dlrn.db import getCommits
from dlrn.db import getLastProcessedCommit
from dlrn.db import getSession
from dlrn.db import Project
from dlrn.reporting import genreports
from dlrn.reporting import get_commit_url
from dlrn.rpmspecfile import RpmSpecCollection
from dlrn.rpmspecfile import RpmSpecFile
from dlrn.utils import dumpshas2file
from dlrn.utils import import_object
from dlrn import version

logging.basicConfig(level=logging.ERROR,
                    format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("dlrn")
logger.setLevel(logging.INFO)


notification_email = """
A build of the package %(name)s has failed against the current master[1] of
the upstream project, please see log[2] and update the packaging[3].

You are receiving this email because you are listed as one of the
maintainers for the %(name)s package[4].

If you have any questions please see the RDO master packaging guide[5] and
feel free to ask questions on the RDO irc channel (#rdo on Freenode).

[1] - %(upstream)s
[2] - %(logurl)s
[3] - %(master-distgit)s
[4] - https://github.com/redhat-openstack/rdoinfo/blob/master/rdo.yml
[5] - https://www.rdoproject.org/packaging/rdo-packaging.html#master-pkg-guide
"""

re_known_errors = re.compile('Error: Nothing to do|'
                             'Error downloading packages|'
                             'No more mirrors to try|'
                             'Cannot retrieve metalink for repository|'
                             'Could not retrieve mirrorlist|'
                             'Failed to synchronize cache for repo|'
                             'No route to host|'
                             'Device or resource busy|'
                             'Could not resolve host')

default_options = {'maxretries': '3', 'tags': None, 'gerrit': None,
                   'templatedir': os.path.join(
                       os.path.dirname(os.path.realpath(__file__)),
                       "templates"),
                   'rsyncdest': '', 'rsyncport': '22',
                   'pkginfo_driver': 'dlrn.drivers.rdoinfo.RdoInfoDriver',
                   'workers': '1',
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
    group.add_argument('--project-name',
                       help="Build a specific project name only.")
    group.add_argument('--package-name',
                       help="Build a specific package name only.")
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

    global options
    options, args = parser.parse_known_args(sys.argv[1:])

    cp = configparser.RawConfigParser(default_options)
    cp.read(options.config_file)

    if options.log_commands is True:
        logging.getLogger("sh.command").setLevel(logging.INFO)
    if options.order is True:
        options.sequential = True

    global session
    session = getSession('sqlite:///commits.sqlite')
    global config_options
    config_options = ConfigOptions(cp)
    pkginfo_driver = config_options.pkginfo_driver
    global pkginfo
    pkginfo = import_object(pkginfo_driver)
    global packages
    packages = pkginfo.getpackages(local_info_repo=options.info_repo,
                                   tags=config_options.tags,
                                   dev_mode=options.dev)

    if options.project_name:
        pkg_names = [p['name'] for p in packages
                     if p['project'] == options.project_name]
    elif options.package_name:
        pkg_names = (options.package_name, )
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
            # This will return all commits since the last handled commit
            # including the last handled commit, remove it later if needed.
            since = "--after=%d" % (commit.dt_commit)
        if not pkg_name or package["name"] == pkg_name:
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

    if options.sequential is True:
        for commit in toprocess:
            status = build_worker(commit)
            exception = status[3]
            if exception is not None:
                logger.error("Received exception %s" % exception)

            post_build(status)
            exit_code = process_build_result(status)
            if options.stop and exit_code != 0:
                return exit_code
    else:
        # Setup multiprocessing pool
        pool = multiprocessing.Pool(config_options.workers)
        iterator = pool.imap(build_worker, toprocess)

        while True:
            try:
                status = iterator.next()
                # Create repo, build versions.csv file.
                # This needs to be sequential
                post_build(status)
                exit_code = process_build_result(status)
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
    genreports(packages, options)
    return exit_code


def process_build_result(status):
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

    if options.run is True:
        if exception is not None:
            exit_code = 1
            if options.stop:
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
            (timesretried(project, commit_hash, commit.distro_hash) <
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
                if options.build_env:
                    env_vars = list(options.build_env)
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
        if options.stop:
            return exit_code
    else:
        commit.status = "SUCCESS"
        commit.notes = notes
        commit.rpms = ",".join(built_rpms)
        session.add(commit)
    if options.dev is False:
        session.commit()
    genreports(packages, options)
    # TODO(jpena): could we launch this asynchronously?
    sync_repo(commit)
    return exit_code


def build_worker(commit):
    if options.run:
        try:
            run(options.run, commit, options.build_env,
                options.dev, options.use_public, options.order,
                do_build=False)
            return [commit, '', '', None]
        except Exception as e:
            return [commit, '', '', e]

    logger.info("Processing %s %s" % (commit.project_name, commit.commit_hash))

    notes = ""
    try:
        built_rpms, notes = build(packages, commit, options.build_env,
                                  options.dev, options.use_public,
                                  options.order)
        return [commit, built_rpms, notes, None]
    except Exception as e:
        return [commit, '', '', e]


def compare():
    parser = argparse.ArgumentParser()
    parser.add_argument('--info-repo',
                        help="use a local rdoinfo repo instead of "
                             "fetching the default one using rdopkg. Only"
                             "applies when pkginfo_driver is rdoinfo in"
                             "projects.ini")

    options, args = parser.parse_known_args(sys.argv[1:])
    pkginfo_driver = config_options.pkginfo_driver
    pkginfo_object = import_object(pkginfo_driver)
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


def sendnotifymail(packages, commit):
    error_details = copy.copy(
        [package for package in packages
            if package["name"] == commit.project_name][0])
    error_details["logurl"] = "%s/%s" % (config_options.baseurl,
                                         commit.getshardedcommitdir())
    error_body = notification_email % error_details

    msg = MIMEText(error_body)
    msg['Subject'] = '[dlrn] %s master package build failed' % \
                     commit.project_name

    email_from = 'no-reply@delorean.com'
    msg['From'] = email_from

    email_to = error_details['maintainers']
    msg['To'] = "packagers"

    if config_options.smtpserver:
        logger.info("Sending notify email to %r" % email_to)
        s = smtplib.SMTP(config_options.smtpserver)
        s.sendmail(email_from, email_to, msg.as_string())
        s.quit()
    else:
        logger.info("Skipping notify email to %r" % email_to)


def refreshrepo(url, path, branch="master", local=False):
    logger.info("Getting %s to %s (%s)" % (url, path, branch))
    checkout_not_present = not os.path.exists(path)
    if checkout_not_present is True:
        sh.git.clone(url, path)
    elif local is False:
        # We need to cover a corner case here, where the repo URL has changed
        # since the last execution
        git = sh.git.bake(_cwd=path, _tty_out=False, _timeout=3600)
        try:
            remotes = git("remote", "-v").splitlines()
            for remote in remotes:
                if '(fetch)' in remote:
                    line = remote.split()
                    if line[1] != url:
                        # URL changed, so remove directory
                        logger.warning("URL for %s changed from %s to %s, "
                                       "cleaning directory and cloning again"
                                       % (path, line[1], url))
                        shutil.rmtree(path)
                        sh.git.clone(url, path)
                    break
        except Exception:
            # Something failed here, maybe this is a failed repo clone
            # Let's warn, remove directory and clone again
            logger.warning("Directory %s does not contain a valid Git repo, "
                           "cleaning directory and cloning again" % path)
            shutil.rmtree(path)
            sh.git.clone(url, path)

    git = sh.git.bake(_cwd=path, _tty_out=False, _timeout=3600)
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
            if "master" in branch:
                # Do not try fallback if already on master branch
                raise
            else:
                # Fallback to master
                if branch.startswith("rpm-"):
                    # TODO(apevec) general distro branch detection
                    branch = "rpm-master"
                else:
                    branch = "master"
                logger.info("Falling back to %s" % branch)
                git.checkout(branch)
        try:
            git.reset("--hard", "origin/%s" % branch)
        except Exception:
            # Maybe it was a tag, not a branch
            git.reset("--hard", "%s" % branch)

    repoinfo = str(git.log("--pretty=format:%H %ct", "-1")).strip().split(" ")
    repoinfo.insert(0, branch)
    return repoinfo


def getdistrobranch(package):
    if 'distro-branch' in package:
        return package['distro-branch']
    else:
        return config_options.distro


def getsourcebranch(package):
    if 'source-branch' in package:
        return package['source-branch']
    else:
        return config_options.source


def process_mock_output(line):
    if options.verbose_mock:
        logger.info(line[:-1])


def run(program, commit, env_vars, dev_mode, use_public, bootstrap,
        do_build=True):

    datadir = os.path.realpath(config_options.datadir)
    yumrepodir = os.path.join("repos", commit.getshardedcommitdir())
    yumrepodir_abs = os.path.join(datadir, yumrepodir)

    commit_hash = commit.commit_hash
    project_name = commit.project_name
    repo_dir = commit.repo_dir

    if do_build:
        # If yum repo already exists remove it and assume we're starting fresh
        if os.path.exists(yumrepodir_abs):
            shutil.rmtree(yumrepodir_abs)
        os.makedirs(yumrepodir_abs)

    sh.git("--git-dir", "%s/.git" % repo_dir,
           "--work-tree=%s" % repo_dir, "reset", "--hard", commit_hash)

    run_cmd = []
    if env_vars:
        for env_var in env_vars:
            run_cmd.append(env_var)

    run_cmd.extend([program,
                    config_options.target, project_name,
                    os.path.join(datadir, yumrepodir),
                    datadir, config_options.baseurl,
                    os.path.realpath(commit.distgit_dir)])
    if not do_build:
        logger.info('Running %s' % ' '.join(run_cmd))

    try:
        sh_version = SemanticVersion.from_pip_string(sh.__version__)
        min_sh_version = SemanticVersion.from_pip_string('1.09')
        if sh_version > min_sh_version:
            sh.env(run_cmd, _err=process_mock_output, _out=process_mock_output)
        else:
            sh.env_(run_cmd, _err=process_mock_output,
                    _out=process_mock_output)
    except Exception as e:
        logger.error('cmd failed. See logs at: %s/%s/' % (datadir,
                                                          yumrepodir))
        raise e


def post_build(status):
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


def build(packages, commit, env_vars, dev_mode, use_public, bootstrap):
    # Set the build timestamp to now
    commit.dt_build = int(time())

    project_name = commit.project_name
    datadir = os.path.realpath(config_options.datadir)
    yumrepodir = os.path.join("repos", commit.getshardedcommitdir())
    yumrepodir_abs = os.path.join(datadir, yumrepodir)

    try:
        build_rpm_wrapper(commit, dev_mode, use_public, bootstrap,
                          env_vars)
    except Exception as e:
        raise Exception("Error in build_rpm_wrapper for %s: %s" %
                        (project_name, e))

    built_rpms = []
    for rpm in os.listdir(yumrepodir_abs):
        if rpm.endswith(".rpm"):
            built_rpms.append(os.path.join(yumrepodir, rpm))
    if not built_rpms:
        raise Exception("No rpms built for %s" % project_name)

    notes = "OK"

    if not os.path.isfile(os.path.join(yumrepodir_abs, "installed")):
        logger.error('Build failed. See logs at: %s/%s/' % (datadir,
                                                            yumrepodir))
        raise Exception("Error installing %s" % project_name)
    else:
        # Overwrite installed file, adding the repo reference
        with open(os.path.join(yumrepodir_abs, "installed"), "w") as fp:
            fp.write("%s %s %s" % (commit.project_name,
                                   commit.commit_hash,
                                   commit.distro_hash))
    return built_rpms, notes


def sync_repo(commit):
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
        # We also need report.html, status_report.html, styles.css and the
        # consistent and current symlinks
        for filename in ['report.html', 'status_report.html', 'styles.css',
                         'consistent', 'current']:
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


def submit_review(commit, env_vars):
    datadir = os.path.realpath(config_options.datadir)
    scriptsdir = os.path.realpath(config_options.scriptsdir)
    yumrepodir = os.path.join("repos", commit.getshardedcommitdir())

    project_name = commit.project_name

    run_cmd = []
    if env_vars:
        for env_var in env_vars:
            run_cmd.append(env_var)

    run_cmd.extend([os.path.join(scriptsdir, "submit_review.sh"),
                    project_name, os.path.join(datadir, yumrepodir),
                    datadir, config_options.baseurl,
                    os.path.realpath(commit.distgit_dir)])
    sh.env(run_cmd)


def isknownerror(logfile):
    # Check log file against known errors
    # Return True if known error, False otherwise
    if not os.path.isfile(logfile):
        return False

    with open(logfile) as fp:
        for line in fp:
            line = line.strip()
            if re_known_errors.search(line):
                # Found a known issue
                return True

    return False


def timesretried(project, commit_hash, distro_hash):
    # Return how many times a commit hash / distro had combination has
    # been retried for a given project

    return session.query(Commit).filter(Commit.project_name == project,
                                        Commit.commit_hash == commit_hash,
                                        Commit.distro_hash == distro_hash,
                                        Commit.status == "RETRY").\
        count()


def build_rpm_wrapper(commit, dev_mode, use_public, bootstrap, env_vars):
    # Get the worker id
    if options.sequential is True:
        worker_id = 1
    else:
        worker_id = multiprocessing.current_process()._identity[0]

    mock_config = "dlrn-" + str(worker_id) + ".cfg"
    scriptsdir = os.path.realpath(config_options.scriptsdir)
    datadir = os.path.realpath(config_options.datadir)
    baseurl = config_options.baseurl
    templatecfg = os.path.join(scriptsdir, config_options.target + ".cfg")
    newcfg = os.path.join(datadir, mock_config + ".new")
    oldcfg = os.path.join(datadir, mock_config)
    shutil.copyfile(templatecfg, newcfg)

    # Add the most current repo, we may have dependencies in it
    if os.path.exists(os.path.join(datadir, "repos", "current", "repodata")):
        with open(newcfg, "r") as fp:
            contents = fp.readlines()
        # delete the last line which must be """
        contents = contents[:-1]
        contents = contents + ["[local]\n", "name=local\n",
                               "baseurl=file://%s/repos/current\n" % datadir,
                               "enabled=1\n", "gpgcheck=0\n", "priority=1\n",
                               "\"\"\""]

    # Set the worker id in the mock configuration, to allow multiple workers
    # for the same config
    with open(newcfg, "r") as fp:
        contents = fp.readlines()
    with open(newcfg, "w") as fp:
        for line in contents:
            if line.startswith("config_opts['root']"):
                line = line[:-2] + "-" + str(worker_id) + "'\n"
            fp.write(line)

    # delete the last line which must be """
    with open(newcfg, "r") as fp:
        contents = fp.readlines()
    contents = contents[:-1]

    r = urllib2.urlopen(baseurl + "/delorean-deps.repo")
    contents = contents + r.readlines()
    contents = contents + ["\n\"\"\""]
    with open(newcfg, "w") as fp:
        fp.writelines(contents)

    if dev_mode or use_public:
        with open(newcfg, "r") as fp:
            contents = fp.readlines()

        # delete the last line which must be """
        contents = contents[:-1]

        r = urllib2.urlopen(baseurl + "/current/delorean.repo")
        contents = contents + r.readlines()
        contents = contents + ["\n\"\"\""]
        with open(newcfg, "w") as fp:
            fp.writelines(contents)

    # don't change dlrn.cfg if the content hasn't changed to prevent
    # mock from rebuilding its cache.
    try:
        if not filecmp.cmp(newcfg, oldcfg):
            shutil.copyfile(newcfg, oldcfg)
    except OSError:
        shutil.copyfile(newcfg, oldcfg)

    # Set env variable for mock configuration
    os.environ['MOCK_CONFIG'] = mock_config

    # if bootstraping, set the appropriate mock config option
    if bootstrap is True:
        os.environ['ADDITIONAL_MOCK_OPTIONS'] = '-D "repo_bootstrap 1"'
    pkginfo.preprocess(package_name=commit.project_name)

    run(os.path.join(scriptsdir, "build_rpm.sh"), commit, env_vars,
        dev_mode, use_public, bootstrap)
