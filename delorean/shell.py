import ConfigParser
import argparse
import os
import sys
import time

import sh

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-file', help="Config File")

    options, args = parser.parse_known_args(sys.argv[1:])
    cp = ConfigParser.RawConfigParser()
    cp.read(options.config_file)

    last_processed_file = os.path.join(cp.get("DEFAULT", "datadir"), "last_processed")
    last_processed = "-1"
    if os.path.exists(last_processed_file):
        fp = open(last_processed_file)
        last_processed = "--after=%s"%fp.read().strip()
        fp.close()

    toprocess = []
    for project in cp.sections():
        repo=cp.get(project, "repo")
        spec=cp.get(project, "spec")
        getinfo(cp, last_processed, project, repo, spec, toprocess)

    toprocess.sort()
    for dt, commit, project in toprocess:
        build(cp, project, commit)
        fp = open(last_processed_file, "w")
        fp.write(str(dt))
        fp.close()

def getinfo(cp, last_processed, project, repo, spec, toprocess):
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

    lines = git.log("--pretty=format:'%ct %H'", last_processed, "--first-parent")
    for line in lines:
        toprocess.append(str(line).strip().strip("'").split(" "))
        toprocess[-1].append(project)
    return toprocess

def getcurrentrpmdir(data, project):
    return os.path.join(data, "current_"+project)

def build(cp, project, commit):
    datadir = os.path.realpath(cp.get("DEFAULT", "datadir"))
    scriptsdir = "/home/derekh/workarea/delorean/scripts" # TODO <---
    yumrepodir = os.path.join("repos", commit[:2], commit[2:4], commit)

    print project, commit
    if not os.path.exists(os.path.join(datadir, yumrepodir)):
        os.makedirs(os.path.join(datadir, yumrepodir))
    if os.path.exists(os.path.join(datadir, yumrepodir, "current.repo")):
        return
    print sh.git("--git-dir", "data/%s/.git"%project, "--work-tree=data/%s"%project, "reset", "--hard", commit)
    try:
        sh.docker("rm", "builder")
    except:
        pass
    print sh.docker("run", "-t", "--volume=%s:/data"%datadir, "--volume=%s:/scripts"%scriptsdir, "--name", "builder", "delorean/fedora", "/scripts/build_rpm_wrapper.sh", project, "/data/%s"%yumrepodir)
    time.sleep(3)
    sh.docker("rm", "builder")

    rpmdir = getcurrentrpmdir(datadir, project)
    if not os.path.exists(rpmdir):
        os.makedirs(rpmdir)

    for rpm in os.listdir(rpmdir):
        os.remove(os.path.join(rpmdir,rpm))

    for rpm in os.listdir(os.path.join(datadir,yumrepodir)):
        os.symlink(os.path.join(datadir,yumrepodir,rpm), os.path.join(rpmdir, os.path.split(rpm)[1]))


    for otherproject in cp.sections():
        if otherproject == project:
            continue
        if os.path.exists(getcurrentrpmdir(datadir, otherproject)):
            for rpm in os.listdir(getcurrentrpmdir(datadir, otherproject)):
                # Don't copy the logs
                print os.path.realpath(os.path.join(getcurrentrpmdir(datadir, otherproject), rpm)), os.path.join(datadir, yumrepodir, rpm)
                if rpm.endswith(".rpm"):
                    os.symlink(os.path.realpath(os.path.join(getcurrentrpmdir(datadir, otherproject), rpm)), os.path.join(datadir, yumrepodir, rpm))


    print sh.createrepo(os.path.join(datadir, yumrepodir))
    fp = open(os.path.join(datadir, yumrepodir, "current.repo"), "w")
    fp.write("""[delorean]
name=delorean-%s-%s
baseurl=%s/%s
enabled=1
gpgcheck=0"""%(project, commit, cp.get("DEFAULT", "baseurl"), yumrepodir))
    fp.close()

    os.symlink(os.path.join(datadir, yumrepodir), os.path.join(datadir, "repos", "current_"))
    os.rename(os.path.join(datadir, "repos", "current_"), os.path.join(datadir, "repos", "current"))
