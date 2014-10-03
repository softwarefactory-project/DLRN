import ConfigParser
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

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import desc

import rdoinfo

Base = declarative_base()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("delorean")


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
    dt_finished = Column(DateTime)
    project_name = Column(String)
    commit_hash = Column(String)
    status = Column(String)
    rpms = Column(String)
    notes = Column(String)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-file', help="Config file")
    parser.add_argument('--build-env', action='append',
                        help="Variables for the build environment.")
    parser.add_argument('--info-file', help="Package info file")
    parser.add_argument('--local', action="store_true",
                        help="Use local git repo's if possible")
    parser.add_argument('--head-only', action="store_true",
                        help="Build from the most recent Git commit only.")
    parser.add_argument('--package-name',
                        help="Build a specific package name only.")

    options, args = parser.parse_known_args(sys.argv[1:])

    package_info = rdoinfo.parse_info_file(options.info_file)

    cp = ConfigParser.RawConfigParser()
    cp.read(options.config_file)

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
            order_by(desc(Commit.dt_commit)).first()
        if commit:
            since = "--after=%d" % (commit.dt_commit + 1)
        repo = package["upstream"]
        spec = package["master-distgit"]
        if not options.package_name or package["name"] == options.package_name:
            project_toprocess = getinfo(cp, project, repo, spec, since,
                                        options.local)
            # If since == -1, then we only want to trigger a build for the
            # most recent change
            if since == "-1" or options.head_only:
                project_toprocess.sort()
                del project_toprocess[:-1]
            toprocess.extend(project_toprocess)

    toprocess.sort()
    for dt, commit, project, repo_dir in toprocess:
        logger.info("Processing %s %s" % (project, commit))
        notes = ""
        try:
            built_rpms, notes = build(cp, package_info, dt,
                                      project, repo_dir, commit,
                                      options.build_env)
        except Exception as e:
            logger.exception("Error while building packages for %s" % project)
            session.add(Commit(dt_commit=dt, project_name=project,
                        commit_hash=commit, status="FAILED",
                        notes=getattr(e, "message", notes)))
            sendnotifymail(cp, package_info, project, commit)
        else:
            session.add(Commit(dt_commit=dt, project_name=project,
                        rpms=",".join(built_rpms), commit_hash=commit,
                        status="SUCCESS", notes=notes))
        session.commit()
        genreport(cp)


def sendnotifymail(cp, package_info, project, commit):
    error_details = copy.copy(
        [package for package in package_info["packages"]
            if package["name"] == project][0])
    error_details["logurl"] = "%s/%s" % (cp.get("DEFAULT", "baseurl"),
            os.path.join("repos", commit[:2], commit[2:4], commit)
    )
    error_body = notification_email % error_details

    msg = MIMEText(error_body)
    msg['Subject'] = '[delorean] %s master package build failed' % project

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
    if local is True:
        return
    git = sh.git.bake(_cwd=path, _tty_out=False)
    git.fetch("origin")
    git.checkout(branch)
    git.reset("--hard", "origin/%s" % branch)


def getinfo(cp, project, repo, spec, since, local=False):
    spec_dir = os.path.join(cp.get("DEFAULT", "datadir"), project+"_spec")
    # TODO : Add support for multiple distros
    spec_branch = cp.get("DEFAULT", "distros")

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
        refreshrepo(repo, repo_dir, local=local)

        git = sh.git.bake(_cwd=repo_dir, _tty_out=False)
        lines = git.log("--pretty=format:'%ct %H'", since, "--first-parent",
                        "origin/master")
        for line in lines:
            project_toprocess.append(str(line).strip().strip("'").split(" "))
            project_toprocess[-1].append(project)
            project_toprocess[-1].append(repo_dir)
            project_toprocess[-1][0] = float(project_toprocess[-1][0])

    return project_toprocess

def testpatches(project, commit, datadir):
    spec_dir = os.path.join(datadir, project+"_spec")
    git = sh.git.bake(_cwd=spec_dir, _tty_out=False)
    try:
        # This remote mightn't exist yet
        git.remote("rm", "upstream")
    except:
        pass

    # If the upstream dir is not a git repo, it contains multiple git repos
    # We don't test patches on these
    if not os.path.isdir(os.path.join(datadir, project, ".git")):
        return
    git.remote("add", "upstream", "-f", "file://%s/%s/" % (datadir, project))
    try:
        git.checkout("master-patches")
    except:
        # This project doesn't have a master-patches branch
        return
    git.reset("--hard", "origin/master-patches")
    try:
        git.rebase(commit)
    except:
        git.rebase("--abort")
        raise Exception("Patches rebase failed")
    git.checkout("f20-master")


def build(cp, package_info, dt, project, repo_dir, commit, env_vars):
    datadir = os.path.realpath(cp.get("DEFAULT", "datadir"))
    # TODO : only working by convention need to improve
    scriptsdir = datadir.replace("data", "scripts")
    yumrepodir = os.path.join("repos", commit[:2], commit[2:4], commit)
    yumrepodir_abs = os.path.join(datadir, yumrepodir)

    # If yum repo already exists remove it and assume we're starting fresh
    if os.path.exists(yumrepodir_abs):
        shutil.rmtree(yumrepodir_abs)
    os.makedirs(yumrepodir_abs)

    # We need to make sure if any patches exist in the master-patches branch
    # they they can still be applied to upstream master, if they can we stop
    testpatches(project, commit, datadir)

    sh.git("--git-dir", "%s/.git" % repo_dir,
           "--work-tree=%s" % repo_dir, "reset", "--hard", commit)
    try:
        sh.docker("kill", "builder")
    except:
        pass

    # looks like we need to give the container time to die
    time.sleep(20)
    try:
        sh.docker("rm", "builder")
    except:
        pass

    docker_run_cmd = []
    # expand the env name=value pairs into docker arguments
    if env_vars:
        for env_var in env_vars:
            docker_run_cmd.append('--env')
            docker_run_cmd.append(env_var)

    docker_run_cmd.extend(["-t", "--volume=%s:/data" % datadir,
                           "--volume=%s:/scripts" % scriptsdir,
                           "--name", "builder", "delorean/fedora",
                           "/scripts/build_rpm_wrapper.sh", project,
                           "/data/%s" % yumrepodir, str(os.getuid()),
                           str(os.getgid())])
    try:
        sh.docker("run", docker_run_cmd)
    except:
        logger.error('Build failed. See logs at: ./data/%s/' % yumrepodir)
        raise Exception("Error while building packages")

    built_rpms = []
    for rpm in os.listdir(yumrepodir_abs):
        if rpm.endswith(".rpm"):
            built_rpms.append(os.path.join(yumrepodir, rpm))
    if not built_rpms:
        raise Exception("No rpms built for %s" % project)

    notes = "OK"
    if not os.path.isfile(os.path.join(yumrepodir_abs, "installed")):
        notes = "Error installing"

    packages = [package["name"] for package in package_info["packages"]]
    for otherproject in packages:
        if otherproject == project:
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
             "gpgcheck=0" % (project, commit, cp.get("DEFAULT", "baseurl"),
                             yumrepodir))
    fp.close()

    current_repo_dir = os.path.join(datadir, "repos", "current")
    os.symlink(os.path.relpath(yumrepodir_abs, os.path.join(datadir, "repos")),
               current_repo_dir+"_")
    os.rename(current_repo_dir+"_", current_repo_dir)
    return built_rpms, notes


def genreport(cp):
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
                    ("%s/%s/%s" % (commit.commit_hash[:2],
                     commit.commit_hash[2:4],
                     commit.commit_hash)))
        html.append("</tr>")
    html.append("</table></html>")

    report_file = os.path.join(cp.get("DEFAULT", "datadir"),
                               "repos", "report.html")
    fp = open(report_file, "w")
    fp.write("".join(html))
    fp.close()
