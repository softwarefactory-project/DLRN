import ConfigParser
import argparse
import logging
import os
import shutil
import sys
import time

import sh

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import desc

Base = declarative_base()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("delorean")


class Commit(Base):
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True)
    dt_commit = Column(Integer)
    dt_finished = Column(DateTime)
    project_name = Column(String)
    commit_hash = Column(String)
    status = Column(String)
    rpms = Column(String)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-file', help="Config File")

    options, args = parser.parse_known_args(sys.argv[1:])
    cp = ConfigParser.RawConfigParser()
    cp.read(options.config_file)

    engine = create_engine('sqlite:///commits.sqlite')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    global session
    session = Session()

    # Build a list of commits we need to process
    toprocess = []
    for project in cp.sections():
        since = "-1"
        commit = session.query(Commit).filter(Commit.project_name == project).\
            order_by(desc(Commit.dt_commit)).first()
        if commit:
            since = "--after=%d" % (commit.dt_commit + 1)
        repo = cp.get(project, "repo")
        spec = cp.get(project, "spec")
        getinfo(cp, project, repo, spec, toprocess, since)

    toprocess.sort()
    for dt, commit, project in toprocess:
        logger.info("Processing %s %s" % (project, commit))
        try:
            built_rpms = build(cp, dt, project, commit)
        except:
            logger.exception("Error while building packages for %s" % project)
            session.add(Commit(dt_commit=dt, project_name=project,
                        commit_hash=commit, status="FAILED"))
        else:
            session.add(Commit(dt_commit=dt, project_name=project,
                        rpms=",".join(built_rpms), commit_hash=commit,
                        status="SUCCESS"))
        session.commit()
        genreport(cp)


def getinfo(cp, project, repo, spec, toprocess, since):
    repo_dir = os.path.join(cp.get("DEFAULT", "datadir"), project)
    spec_dir = os.path.join(cp.get("DEFAULT", "datadir"), project+"_spec")

    # Get the most uptodate spec
    if not os.path.exists(spec_dir):
        sh.git.clone(spec, spec_dir)
    git = sh.git.bake(_cwd=spec_dir, _tty_out=False)
    git.fetch("origin")
    git.reset("--hard", "origin/master")

    # Get the most uptodate source
    if not os.path.exists(repo_dir):
        sh.git.clone(repo, repo_dir)

    git = sh.git.bake(_cwd=repo_dir, _tty_out=False)
    git.fetch("origin")

    lines = git.log("--pretty=format:'%ct %H'", since, "--first-parent",
                    "origin/master")
    for line in lines:
        toprocess.append(str(line).strip().strip("'").split(" "))
        toprocess[-1].append(project)
        toprocess[-1][0] = float(toprocess[-1][0])
    return toprocess


def build(cp, dt, project, commit):
    datadir = os.path.realpath(cp.get("DEFAULT", "datadir"))
    # TODO : only working by convention need to improve
    scriptsdir = datadir.replace("data", "scripts")
    yumrepodir = os.path.join("repos", commit[:2], commit[2:4], commit)
    yumrepodir_abs = os.path.join(datadir, yumrepodir)

    # If yum repo already exists remove it and assume we're starting fresh
    if os.path.exists(yumrepodir_abs):
        shutil.rmtree(yumrepodir_abs)
    os.makedirs(yumrepodir_abs)

    sh.git("--git-dir", "data/%s/.git" % project,
           "--work-tree=data/%s" % project, "reset", "--hard", commit)
    try:
        sh.docker("rm", "builder")
    except:
        pass
    sh.docker("run", "-t", "--volume=%s:/data" % datadir,
              "--volume=%s:/scripts" % scriptsdir,
              "--name", "builder", "delorean/fedora",
              "/scripts/build_rpm_wrapper.sh", project,
              "/data/%s" % yumrepodir)

    time.sleep(3)
    sh.docker("rm", "builder")

    built_rpms = []
    for rpm in os.listdir(yumrepodir_abs):
        if rpm.endswith(".rpm"):
            built_rpms.append(os.path.join(yumrepodir, rpm))

    for otherproject in cp.sections():
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
            os.symlink(os.path.relpath(os.path.join(datadir, rpm), yumrepodir_abs), rpm_link_src)

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
    return built_rpms


def genreport(cp):
    html = ["<html><head/><body><table>"]
    commits = session.query(Commit).order_by(desc(Commit.dt_commit)).limit(300)
    for commit in commits:
        html.append("<tr>")
        html.append("<td>%s</td>" % time.ctime(commit.dt_commit))
        html.append("<td>%s</td>" % commit.project_name)
        html.append("<td>%s</td>" % commit.commit_hash)
        html.append("<td>%s</td>" % commit.status)
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
