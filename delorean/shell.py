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
import logging
import os
import re
import shutil
import smtplib
import sys
from time import time

from email.mime.text import MIMEText
from pbr.version import SemanticVersion

from prettytable import PrettyTable
import sh
from six.moves import configparser

import rdopkg.utils.log
rdopkg.utils.log.set_colors('no')
from rdopkg.actionmods import rdoinfo

from delorean.db import Commit
from delorean.db import getCommits
from delorean.db import getLastProcessedCommit
from delorean.db import getSession
from delorean.db import Project
from delorean.reporting import genreports
from delorean.rpmspecfile import RpmSpecCollection
from delorean.rpmspecfile import RpmSpecFile
from delorean.utils import dumpshas2file
from delorean import version

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("delorean")
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
                             'Failed to synchronize cache for repo|'
                             'No route to host|'
                             'Device or resource busy|'
                             'Could not resolve host')

default_options = {'maxretries': '3', 'tags': None,
                   'templatedir': os.path.join(
                       os.path.dirname(os.path.realpath(__file__)),
                       "templates")
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
                             "fetching the default one using rdopkg.")
    parser.add_argument('--build-env', action='append',
                        help="Variables for the build environment.")
    parser.add_argument('--local', action="store_true",
                        help="Use local git repos if possible.")
    parser.add_argument('--head-only', action="store_true",
                        help="Build from the most recent Git commit only.")
    parser.add_argument('--package-name',
                        help="Build a specific package name only.")
    parser.add_argument('--dev', action="store_true",
                        help="Don't reset packaging git repo, force build "
                             "and add public master repo for dependencies "
                             "(dev mode).")
    parser.add_argument('--log-commands', action="store_true",
                        help="Log the commands run by delorean.")
    parser.add_argument('--use-public', action="store_true",
                        help="Use the public master repo for dependencies "
                             "when doing install verification.")
    parser.add_argument('--order', action="store_true",
                        help="Compute the build order according to the spec "
                             "files instead of the dates of the commits.")
    parser.add_argument('--status', action="store_true",
                        help="Get the status of packages.")
    parser.add_argument('--recheck', action="store_true",
                        help="Force a rebuild for a particular package. "
                        "Imply --package-name")
    parser.add_argument('--version',
                        action='version',
                        version=version.version_info.version_string())

    options, args = parser.parse_known_args(sys.argv[1:])

    cp = configparser.RawConfigParser(default_options)
    cp.read(options.config_file)

    if options.log_commands is True:
        logging.getLogger("sh.command").setLevel(logging.INFO)

    global session
    session = getSession('sqlite:///commits.sqlite')
    packages = getpackages(local_info_repo=options.info_repo,
                           tags=cp.get("DEFAULT", "tags"))

    if options.status is True:
        if options.package_name:
            names = (options.package_name, )
        else:
            names = [p['name'] for p in packages]
        for name in names:
            commit = getLastProcessedCommit(session, name, 'invalid status')
            if commit:
                print(name, commit.status)
            else:
                print(name, 'NO_BUILD')
        sys.exit(0)

    if options.recheck is True:
        if not options.package_name:
            logger.error('Please use --package-name with --recheck.')
            sys.exit(1)
        commit = getLastProcessedCommit(session, options.package_name)
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
                             % options.package_name)
                sys.exit(1)

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
        repo = package["upstream"]
        distro = package["master-distgit"]
        if not options.package_name or package["name"] == options.package_name:
            project_toprocess = getinfo(cp, project, repo, distro, since,
                                        options.local, options.dev, package)
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
                if (options.dev is True) or \
                   (not session.query(Commit).filter(
                        Commit.project_name == project,
                        Commit.commit_hash == commit_toprocess.commit_hash,
                        Commit.distro_hash == commit_toprocess.distro_hash,
                        Commit.status != "RETRY")
                        .all()):
                    toprocess.append(commit_toprocess)

    # if requested do a sort according to build and install
    # dependencies
    if options.order is True and not options.package_name:
        # collect info from all spec files
        logger.info("Reading rpm spec files")
        projects = sorted([p['name'] for p in packages])
        specs = RpmSpecCollection([RpmSpecFile(
            open(os.path.join(cp.get("DEFAULT", "datadir"),
                              project_name + "_distro",
                              project_name + '.spec')).read(-1))
            for project_name in projects])
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
    for commit in toprocess:
        project = commit.project_name

        project_info = session.query(Project).filter(
            Project.project_name == project).first()
        if not project_info:
            project_info = Project(project_name=project, last_email=0)

        commit_hash = commit.commit_hash

        logger.info("Processing %s %s" % (project, commit_hash))
        notes = ""
        try:
            built_rpms, notes = build(cp, packages,
                                      commit, options.build_env, options.dev,
                                      options.use_public)
        except Exception as e:
            exit_code = 1
            datadir = os.path.realpath(cp.get("DEFAULT", "datadir"))
            logfile = os.path.join(datadir, "repos",
                                   commit.getshardedcommitdir(),
                                   "rpmbuild.log")
            max_retries = cp.getint("DEFAULT", "maxretries")
            if isknownerror(logfile) and \
               (timesretried(project, commit_hash, commit.distro_hash)
               < max_retries):
                logger.exception("Known error building packages for %s,"
                                 " will retry later" % project)
                commit.status = "RETRY"
                commit.notes = getattr(e, "message", notes)
                session.add(commit)
            else:
                logger.exception("Error while building packages for %s"
                                 % project)
                commit.status = "FAILED"
                commit.notes = getattr(e, "message", notes)
                session.add(commit)

                # If the log file hasn't been created we add what we have
                # This happens if the rpm build script didn't run.
                if not os.path.exists(logfile):
                    with open(logfile, "w") as fp:
                        fp.write(getattr(e, "message", notes))

                if not project_info.suppress_email():
                    sendnotifymail(cp, packages, commit)
                    project_info.sent_email()
                    session.add(project_info)
        else:
            commit.status = "SUCCESS"
            commit.notes = notes
            commit.rpms = ",".join(built_rpms)
            session.add(commit)
        if options.dev is False:
            session.commit()
        genreports(cp, packages, options)
    genreports(cp, packages, options)
    return exit_code


def compare():
    parser = argparse.ArgumentParser()
    parser.add_argument('--info-repo',
                        help="use local rdoinfo repo instead of"
                             "fetching default one using rdopkg")
    options, args = parser.parse_known_args(sys.argv[1:])

    packages = getpackages(local_info_repo=options.info_repo,
                           tags=cp.get("DEFAULT", "tags"))
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


def getpackages(local_info_repo=None, tags=None):
    inforepo = None
    if local_info_repo:
        inforepo = rdoinfo.RdoinfoRepo(local_repo_path=local_info_repo,
                                       apply_tag=tags)
    else:
        inforepo = rdoinfo.get_default_inforepo(apply_tag=tags)
        # rdopkg will clone/pull rdoinfo repo as needed (~/.rdopkg/rdoinfo)
        inforepo.init()
    pkginfo = inforepo.get_info()
    packages = pkginfo["packages"]
    if tags:
        # FIXME allow list of tags?
        packages = rdoinfo.filter_pkgs(packages, {'tags': tags})
    return packages


def sendnotifymail(cp, packages, commit):
    error_details = copy.copy(
        [package for package in packages
            if package["name"] == commit.project_name][0])
    error_details["logurl"] = "%s/%s" % (cp.get("DEFAULT", "baseurl"),
                                         commit.getshardedcommitdir())
    error_body = notification_email % error_details

    msg = MIMEText(error_body)
    msg['Subject'] = '[delorean] %s master package build failed' % \
                     commit.project_name

    email_from = 'no-reply@delorean.com'
    msg['From'] = email_from

    email_to = error_details['maintainers']
    msg['To'] = "packagers"

    smtpserver = cp.get("DEFAULT", "smtpserver")
    if smtpserver:
        logger.info("Sending notify email to %r" % email_to)
        s = smtplib.SMTP(cp.get("DEFAULT", "smtpserver"))
        s.sendmail(email_from, email_to, msg.as_string())
        s.quit()
    else:
        logger.info("Skipping notify email to %r" % email_to)


def refreshrepo(url, path, branch="master", local=False):
    logger.info("Getting %s to %s" % (url, path))
    if not os.path.exists(path):
        sh.git.clone(url, path)

    git = sh.git.bake(_cwd=path, _tty_out=False, _timeout=3600)
    if local is False:
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
        git.checkout(branch)
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
    git.reset("--hard", "origin/%s" % branch)
    repoinfo = str(git.log("--pretty=format:%H %ct", "-1")).strip().split(" ")
    repoinfo.insert(0, branch)
    return repoinfo


def getdistrobranch(cp, package):
    if 'distro-branch' in package:
        return package['distro-branch']
    else:
        return cp.get("DEFAULT", "distro")


def getsourcebranch(cp, package):
    if 'source-branch' in package:
        return package['source-branch']
    else:
        return cp.get("DEFAULT", "source")


def getinfo(cp, project, repo, distro, since, local, dev_mode, package):
    distro_dir = os.path.join(cp.get("DEFAULT", "datadir"),
                              project + "_distro")
    distro_branch = getdistrobranch(cp, package)
    source_branch = getsourcebranch(cp, package)

    if dev_mode is False:
        distro_branch, distro_hash, dt_distro = refreshrepo(
            distro, distro_dir, distro_branch, local=local)
    else:
        distro_hash = "dev"
        dt_distro = 0  # Doesn't get used in dev mode
        if not os.path.isdir(distro_dir):
            refreshrepo(distro, distro_dir, distro_branch, local=local)

    # repo is usually a string, but if it contains more then one entry we
    # git clone into a project subdirectory
    repos = [repo]
    if isinstance(repo, list):
        repos = repo
    project_toprocess = []
    for repo in repos:
        repo_dir = os.path.join(cp.get("DEFAULT", "datadir"), project)
        if len(repos) > 1:
            repo_dir = os.path.join(repo_dir, os.path.split(repo)[1])
        source_branch, _, _ = refreshrepo(repo, repo_dir, source_branch,
                                          local=local)

        git = sh.git.bake(_cwd=repo_dir, _tty_out=False)
        # Git gives us commits already sorted in the right order
        lines = git.log("--pretty=format:'%ct %H'", since, "--first-parent",
                        "--reverse", "origin/%s" % source_branch)

        for line in lines:
            dt, commit_hash = str(line).strip().strip("'").split(" ")
            commit = Commit(dt_commit=float(dt), project_name=project,
                            commit_hash=commit_hash, repo_dir=repo_dir,
                            distro_hash=distro_hash, dt_distro=dt_distro)
            project_toprocess.append(commit)

    return project_toprocess


def build(cp, packages, commit, env_vars, dev_mode, use_public):

    # Set the build timestamp to now
    commit.dt_build = int(time())

    datadir = os.path.realpath(cp.get("DEFAULT", "datadir"))
    scriptsdir = os.path.realpath(cp.get("DEFAULT", "scriptsdir"))
    target = cp.get("DEFAULT", "target")
    yumrepodir = os.path.join("repos", commit.getshardedcommitdir())
    yumrepodir_abs = os.path.join(datadir, yumrepodir)
    baseurl = cp.get("DEFAULT", "baseurl")

    commit_hash = commit.commit_hash
    project_name = commit.project_name
    repo_dir = commit.repo_dir

    # If yum repo already exists remove it and assume we're starting fresh
    if os.path.exists(yumrepodir_abs):
        shutil.rmtree(yumrepodir_abs)
    os.makedirs(yumrepodir_abs)

    sh.git("--git-dir", "%s/.git" % repo_dir,
           "--work-tree=%s" % repo_dir, "reset", "--hard", commit_hash)

    run_cmd = []
    # expand the env name=value pairs into docker arguments
    if env_vars:
        for env_var in env_vars:
            run_cmd.append(env_var)
    if (dev_mode or use_public):
            run_cmd.append("DELOREAN_DEV=1")

    run_cmd.extend([os.path.join(scriptsdir, "build_rpm_wrapper.sh"),
                    target, project_name,
                    os.path.join(datadir, yumrepodir),
                    datadir, baseurl])
    try:
        sh_version = SemanticVersion.from_pip_string(sh.__version__)
        min_sh_version = SemanticVersion.from_pip_string('1.09')
        if sh_version > min_sh_version:
            sh.env(run_cmd)
        else:
            sh.env_(run_cmd)
    except Exception as e:
        logger.error('cmd failed. See logs at: %s/%s/' % (datadir,
                                                          yumrepodir))
        raise e

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

    shafile = open(os.path.join(yumrepodir_abs, "versions.csv"), "w")
    shafile.write("Project,Source Repo,Source Sha,Dist Repo,Dist Sha,Status\n")

    failures = 0

    for otherproject in packages:
        otherprojectname = otherproject["name"]
        if otherprojectname == project_name:
            # Output sha's this project
            dumpshas2file(shafile, commit, otherproject["upstream"],
                          otherproject["master-distgit"], "SUCCESS")
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
            dumpshas2file(shafile, last, otherproject["upstream"],
                          otherproject["master-distgit"],
                          last_processed.status)
            if last_processed.status != 'SUCCESS':
                failures += 1
        else:
            failures += 1
    shafile.close()

    sh.createrepo(yumrepodir_abs)

    with open(os.path.join(
            yumrepodir_abs, "%s.repo" % cp.get("DEFAULT", "reponame")),
            "w") as fp:
        fp.write("[%s]\nname=%s-%s-%s\nbaseurl=%s/%s\nenabled=1\n"
                 "gpgcheck=0\npriority=1" % (cp.get("DEFAULT", "reponame"),
                                             cp.get("DEFAULT", "reponame"),
                                             project_name, commit_hash,
                                             cp.get("DEFAULT", "baseurl"),
                                             commit.getshardedcommitdir()))

    dirnames = ['current']
    if failures == 0:
        dirnames.append('consistent')
    else:
        logger.info('%d packages not built correctly: not updating the '
                    'consistent symlink' % failures)
    for dirname in dirnames:
        target_repo_dir = os.path.join(datadir, "repos", dirname)
        os.symlink(os.path.relpath(yumrepodir_abs,
                                   os.path.join(datadir, "repos")),
                   target_repo_dir + "_")
        os.rename(target_repo_dir + "_", target_repo_dir)
    return built_rpms, notes


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
