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


import argparse
import copy
import logging
import os
import shutil
import smtplib
import sys
import time

from email.mime.text import MIMEText

import sh
from six.moves import configparser

from sqlalchemy import create_engine, Column, desc, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import rdopkg.utils.log
rdopkg.utils.log.set_colors('no')
from rdopkg.actionmods import rdoinfo
import rdopkg.conf

Base = declarative_base()

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("delorean")
logger.setLevel(logging.INFO)


notification_email = """
A build of the package %(name)s has failed against the current master[1] of
the upstream project, please see log[2] and update the packaging[3].

You are receiving this email because you are listed as one of the
maintainers for the %(name)s package[4].

If you have any questions please see the FAQ[5], feel free to ask new questions
on there and we will add the answer as soon as possible.

[1] - %(upstream)s
[2] - %(logurl)s
[3] - %(master-distgit)s
[4] - https://github.com/redhat-openstack/rdoinfo/blob/master/rdo.yml
[5] - https://etherpad.openstack.org/p/delorean-packages
"""


class Commit(Base):
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True)
    dt_commit = Column(Integer)
    project_name = Column(String)
    repo_dir = Column(String)
    commit_hash = Column(String)
    spec_hash = Column(String)
    status = Column(String)
    rpms = Column(String)
    notes = Column(String)

    def __cmp__(self, b):
        return cmp(self.dt_commit, b.dt_commit)

    def getshardedcommitdir(self):
        spec_hash_suffix = ""
        if self.spec_hash:
            spec_hash_suffix = "_%s" % self.spec_hash[:8]
        return os.path.join(self.commit_hash[:2], self.commit_hash[2:4],
                            self.commit_hash + spec_hash_suffix)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    project_name = Column(String)
    last_email = Column(Integer)

    # Returns True if the last email sent for this project
    # was less then 24 hours ago
    def suppress_email(self):
        ct = time.time()
        if ct - self.last_email > 86400:
            return False
        return True

    def sent_email(self):
        self.last_email = int(time.time())


def main():
    parser = argparse.ArgumentParser()
    # Some of the non-positional arguments are required, so change the text
    # saying "optional arguments" to just "arguments":
    parser._optionals.title = 'arguments'

    parser.add_argument('--config-file',
                        help="Config file (required)",
                        required=True)
    parser.add_argument('--info-repo',
                        help="use local rdoinfo repo instead of"
                             "fetching default one using rdopkg")
    parser.add_argument('--build-env', action='append',
                        help="Variables for the build environment.")
    parser.add_argument('--local', action="store_true",
                        help="Use local git repos if possible")
    parser.add_argument('--head-only', action="store_true",
                        help="Build from the most recent Git commit only.")
    parser.add_argument('--package-name',
                        help="Build a specific package name only.")
    parser.add_argument('--dev', action="store_true",
                        help="Don't reset packaging git repo, force build "
                             "and add public master repo for dependencies "
                             "(dev mode).")

    options, args = parser.parse_known_args(sys.argv[1:])

    cp = configparser.RawConfigParser()
    cp.read(options.config_file)

    package_info = getpkginfo(local_info_repo=options.info_repo)

    engine = create_engine('sqlite:///commits.sqlite')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    global session
    session = Session()

    # Build a list of commits we need to process
    toprocess = []
    for package in package_info["packages"]:
        project = package["name"]
        since = "-1"
        commit = session.query(Commit).filter(Commit.project_name == project).\
            order_by(desc(Commit.dt_commit)).\
            order_by(desc(Commit.id)).first()
        if commit:
            # This will return all commits since the last handled commit
            # including the last handled commit, remove it later if needed.
            since = "--after=%d" % (commit.dt_commit)
        repo = package["upstream"]
        spec = package["master-distgit"]
        if not options.package_name or package["name"] == options.package_name:
            project_toprocess = getinfo(cp, project, repo, spec, since,
                                        options.local, options.dev, package)
            # If since == -1, then we only want to trigger a build for the
            # most recent change
            if since == "-1" or options.head_only:
                del project_toprocess[:-1]

            # The first entry in the list of commits is a commit we have
            # already processed, we want to process it again only if in dev
            # mode or spec hash has changed, we can't simply check against the
            # last commit in the db, as multiple commits can have the same
            # commit date
            for commit_toprocess in project_toprocess:
                if (options.dev is True) or \
                   (not session.query(Commit).filter(
                        Commit.project_name == project,
                        Commit.commit_hash == commit_toprocess.commit_hash,
                        Commit.spec_hash == commit_toprocess.spec_hash).all()):
                    toprocess.append(commit_toprocess)

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
            built_rpms, notes = build(cp, package_info,
                                      commit, options.build_env, options.dev)
        except Exception as e:
            exit_code = 1
            logger.exception("Error while building packages for %s" % project)
            commit.status = "FAILED"
            commit.notes = getattr(e, "message", notes)
            session.add(commit)

            # If the log file hasn't been created we add what we have
            # This happens if the rpm build script didn't run.
            datadir = os.path.realpath(cp.get("DEFAULT", "datadir"))
            logfile = os.path.join(datadir, "repos",
                                   commit.getshardedcommitdir(),
                                   "rpmbuild.log")
            if not os.path.exists(logfile):
                fp = open(logfile, "w")
                fp.write(getattr(e, "message", notes))
                fp.close()

            if not project_info.suppress_email():
                sendnotifymail(cp, package_info, commit)
                project_info.sent_email()
        else:
            commit.status = "SUCCESS"
            commit.notes = notes
            commit.rpms = ",".join(built_rpms)
            session.add(commit)
        if options.dev is False:
            session.commit()
        genreports(cp, package_info)
    genreports(cp, package_info)
    return exit_code


def getpkginfo(local_info_repo=None):
    inforepo = None
    if local_info_repo:
        inforepo = rdoinfo.RdoinfoRepo(local_repo_path=local_info_repo,
                                       verbose=False)
    else:
        inforepo = rdoinfo.RdoinfoRepo(rdopkg.conf.cfg['HOME_DIR'],
                                       rdopkg.conf.cfg['RDOINFO_REPO'],
                                       verbose=False)
        # rdopkg will clone/pull rdoinfo repo as needed (~/.rdopkg/rdoinfo)
        inforepo.init()
    return inforepo.get_info()


def sendnotifymail(cp, package_info, commit):
    error_details = copy.copy(
        [package for package in package_info["packages"]
            if package["name"] == commit.project_name][0])
    error_details["logurl"] = "%s/%s" % (cp.get("DEFAULT", "baseurl"),
                                         os.path.join("repos",
                                         commit.getshardedcommitdir()))
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
        sh.git.clone(url, path, "-b", branch)

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
    git.checkout(branch)
    git.reset("--hard", "origin/%s" % branch)
    return str(git("rev-parse", "HEAD")).strip()


def getspecbranch(cp, package):
    if 'spec-branch' in package:
        return package['spec-branch']
    else:
        return cp.get("DEFAULT", "distros")


def getsourcebranch(cp, package):
    if 'source-branch' in package:
        return package['source-branch']
    else:
        return cp.get("DEFAULT", "source")


def getinfo(cp, project, repo, spec, since, local, dev_mode, package):
    spec_dir = os.path.join(cp.get("DEFAULT", "datadir"), project + "_spec")
    # TODO(someone) : Add support for multiple distros
    spec_branch = getspecbranch(cp, package)
    source_branch = getsourcebranch(cp, package)

    if dev_mode is False:
        spec_hash = refreshrepo(spec, spec_dir, spec_branch, local=local)
    else:
        spec_hash = "dev"
        if not os.path.isdir(spec_dir):
            refreshrepo(spec, spec_dir, spec_branch, local=local)

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
        refreshrepo(repo, repo_dir, source_branch, local=local)

        git = sh.git.bake(_cwd=repo_dir, _tty_out=False)
        lines = git.log("--pretty=format:'%ct %H'", since, "--first-parent",
                        "origin/%s" % source_branch)
        for line in lines:
            dt, commit_hash = str(line).strip().strip("'").split(" ")
            commit = Commit(dt_commit=float(dt), project_name=project,
                            commit_hash=commit_hash, repo_dir=repo_dir,
                            spec_hash=spec_hash)
            project_toprocess.append(commit)
    project_toprocess.sort()
    return project_toprocess


def build(cp, package_info, commit, env_vars, dev_mode):
    datadir = os.path.realpath(cp.get("DEFAULT", "datadir"))
    scriptsdir = os.path.realpath(cp.get("DEFAULT", "scriptsdir"))
    target = cp.get("DEFAULT", "target")
    yumrepodir = os.path.join("repos", commit.getshardedcommitdir())
    yumrepodir_abs = os.path.join(datadir, yumrepodir)

    commit_hash = commit.commit_hash
    project_name = commit.project_name
    repo_dir = commit.repo_dir

    # If yum repo already exists remove it and assume we're starting fresh
    if os.path.exists(yumrepodir_abs):
        shutil.rmtree(yumrepodir_abs)
    os.makedirs(yumrepodir_abs)

    sh.git("--git-dir", "%s/.git" % repo_dir,
           "--work-tree=%s" % repo_dir, "reset", "--hard", commit_hash)

    docker_run_cmd = []
    # expand the env name=value pairs into docker arguments
    if env_vars:
        for env_var in env_vars:
            docker_run_cmd.append('--env')
            docker_run_cmd.append(env_var)
    if dev_mode is True:
            docker_run_cmd.append('--env')
            docker_run_cmd.append("DELOREAN_DEV=1")

    docker_run_cmd.extend(["-t", "--volume=%s:/data" % datadir,
                           "--volume=%s:/scripts" % scriptsdir,
                           "--name", "builder-%s" % target,
                           "delorean/%s" % target,
                           "/scripts/build_rpm_wrapper.sh", project_name,
                           "/data/%s" % yumrepodir, str(os.getuid()),
                           str(os.getgid())])
    try:
        sh.docker("run", docker_run_cmd)
    except Exception as e:
        logger.error('Docker cmd failed. See logs at: %s/%s/' % (datadir,
                                                                 yumrepodir))
        raise e
    finally:
        # Kill builder-"target" if running and remove if present
        try:
            sh.docker("kill", "builder-%s" % target)
            sh.docker("wait", "builder-%s" % target)
        except Exception:
            pass
        try:
            sh.docker("rm", "builder-%s" % target)
        except Exception:
            pass

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

    packages = [package["name"] for package in package_info["packages"]]
    for otherproject in packages:
        if otherproject == project_name:
            continue
        last_success = session.query(Commit).\
            filter(Commit.project_name == otherproject).\
            filter(Commit.status == "SUCCESS").\
            order_by(desc(Commit.dt_commit)).first()
        if not last_success:
            continue
        rpms = last_success.rpms.split(",")
        for rpm in rpms:
            rpm_link_src = os.path.join(yumrepodir_abs, os.path.split(rpm)[1])
            os.symlink(os.path.relpath(os.path.join(datadir, rpm),
                       yumrepodir_abs), rpm_link_src)

    sh.createrepo(yumrepodir_abs)

    fp = open(os.path.join(yumrepodir_abs, "delorean.repo"), "w")
    fp.write("[delorean]\nname=delorean-%s-%s\nbaseurl=%s/%s\nenabled=1\n"
             "gpgcheck=0\npriority=1" % (project_name, commit_hash,
                                         cp.get("DEFAULT", "baseurl"),
                                         commit.getshardedcommitdir()))
    fp.close()

    current_repo_dir = os.path.join(datadir, "repos", "current")
    os.symlink(os.path.relpath(yumrepodir_abs, os.path.join(datadir, "repos")),
               current_repo_dir + "_")
    os.rename(current_repo_dir + "_", current_repo_dir)
    return built_rpms, notes


def genreports(cp, package_info):
    # Generate report of the last 300 package builds
    html = ["<html><head/><body><table>"]
    commits = session.query(Commit).order_by(desc(Commit.dt_commit)).limit(300)
    for commit in commits:
        html.append("<tr>")
        html.append("<td>%s</td>" % time.ctime(commit.dt_commit))
        html.append("<td>%s</td>" % commit.project_name)
        html.append("<td>%s</td>" % commit.commit_hash)
        html.append("<td>%s</td>" % commit.status)
        html.append("<td>%s</td>" % commit.notes[:50])
        html.append("<td><a href=\"%s\">repo</a></td>" %
                    commit.getshardedcommitdir())
        html.append("<td><a href=\"%s/spec_delta.diff\">spec delta</a></td>" %
                    commit.getshardedcommitdir())
        html.append("</tr>")
    html.append("</table></html>")

    report_file = os.path.join(cp.get("DEFAULT", "datadir"),
                               "repos", "report.html")
    fp = open(report_file, "w")
    fp.write("".join(html))
    fp.close()

    # Generate report of status for each project
    html = ["<html><head/><body><table>"]
    html.append("<tr><td>Name</td><td>Failures</td><td>Last Success</td></tr>")
    packages = [package for package in package_info["packages"]]
    # Find the most recent successfull build
    # then report on failures since then
    for package in packages:
        name = package["name"]
        commits = session.query(Commit).filter(Commit.project_name == name).\
            filter(Commit.status == "SUCCESS").\
            order_by(desc(Commit.dt_commit)).limit(1)
        last_success = commits.first()
        last_success_dt = 0
        if last_success is not None:
            last_success_dt = last_success.dt_commit

        commits = session.query(Commit).filter(Commit.project_name == name).\
            filter(Commit.status == "FAILED",
                   Commit.dt_commit > last_success_dt)
        if commits.count() == 0:
            continue

        html.append("<tr>")
        html.append("<td>%s</td>" % name)
        html.append("<td>%s</td>" % commits.count())
        html.append("<td>%s</td>" % time.ctime(last_success_dt))
        html.append("</tr>")
    html.append("</table></html>")

    report_file = os.path.join(cp.get("DEFAULT", "datadir"),
                               "repos", "status_report.html")
    fp = open(report_file, "w")
    fp.write("".join(html))
    fp.close()
