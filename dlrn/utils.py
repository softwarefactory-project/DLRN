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
import fcntl
import hashlib
import logging
import os
import re
import sh
import sys
import yaml

import sqlalchemy

from contextlib import contextmanager
from dlrn.db import CIVote
from dlrn.db import CIVote_Aggregate
from dlrn.db import Commit
from dlrn.db import getSession
from dlrn.db import Project
from dlrn.db import Promotion
from dlrn.db import User

re_known_errors = re.compile('Error: Nothing to do|'
                             'Error downloading packages|'
                             'No more mirrors to try|'
                             'Cannot retrieve metalink for repository|'
                             'Could not retrieve mirrorlist|'
                             'Failed to synchronize cache for repo|'
                             'No route to host|'
                             'Device or resource busy|'
                             'Could not resolve host|'
                             'Temporary failure in name resolution|'
                             'distroinfo.exception.CommandFailed: Command '
                             'failed with return code 128: git|'
                             'Error fetching remote|'
                             'Connection timed out')


logger = logging.getLogger("dlrn-utils")


# Import a Python class
def import_class(import_str):
    mod_str, _sep, class_str = import_str.rpartition('.')
    __import__(mod_str)
    try:
        myclass = getattr(sys.modules[mod_str], class_str)
        return myclass
    except AttributeError:
        raise ImportError('Cannot find class %s' % class_str)


# Import a Python object
def import_object(import_str, *args, **kwargs):
    myclass = import_class(import_str)
    return myclass(*args, **kwargs)


# Load a yaml file into a db session, used to populate a in memory database
# during tests
def loadYAML(session, yamlfile):
    with open(yamlfile) as fp:
        data = yaml.safe_load(fp)

    try:
        for user in data['users']:
            my_user = User(**user)
            session.add(my_user)
            session.commit()
    except KeyError:
        pass   # No users in yaml, just ignore
    for commit in data['commits']:
        c = Commit(**commit)
        # We need a special case for extended_hash, which could be "None"
        if c.extended_hash == 'None':
            c.extended_hash = None
        # Retro compatibility before commit type
        if not c.type:
            c.type = "rpm"
        session.add(c)
        session.commit()
    try:
        for project in data['projects']:
            p = Project(**project)
            session.add(p)
            session.commit()
    except KeyError:
        pass   # No projects in yaml, just ignore
    try:
        for civote in data['civotes']:
            vote = CIVote(**civote)
            session.add(vote)
            session.commit()
    except KeyError:
        pass   # No civotes in yaml, just ignore
    try:
        for civote in data['civotes_agg']:
            vote = CIVote_Aggregate(**civote)
            session.add(vote)
            session.commit()
    except KeyError:
        pass   # No civotes_agg in yaml, just ignore
    try:
        for promotion in data['promotions']:
            p = Promotion(**promotion)
            session.add(p)
            session.commit()
    except KeyError:
        pass   # No promotions in yaml, just ignore

    session.commit()


# Load a yaml file into a list of commits
def loadYAML_list(yamlfile):
    with open(yamlfile) as fp:
        data = yaml.safe_load(fp)

    commit_list = []
    for commit in data['commits']:
        c = Commit(**commit)
        # We need a special case for extended_hash, which could be "None"
        if c.extended_hash == 'None':
            c.extended_hash = None
        # Retro compatibility before commit type
        if not c.type:
            c.type = "rpm"
        commit_list.append(c)

    return commit_list


# Save a database to yaml, this is a helper function to assist in creating
# yaml files for unit tests.
def saveYAML(session, yamlfile):
    data = {}

    attrs = []
    for a in dir(Commit):
        if type(getattr(Commit, a)) == \
                sqlalchemy.orm.attributes.InstrumentedAttribute:
            attrs.append(a)
    data['commits'] = []
    for commit in session.query(Commit).all():
        d = {}
        for a in attrs:
            d[a] = str(getattr(commit, a))
        data['commits'].append(d)

    attrs = []
    for a in dir(Project):
        if type(getattr(Project, a)) == \
                sqlalchemy.orm.attributes.InstrumentedAttribute:
            attrs.append(a)
    data['projects'] = []
    for project in session.query(Project).all():
        d = {}
        for a in attrs:
            d[a] = str(getattr(project, a))
        data['projects'].append(d)

    attrs = []
    for a in dir(CIVote):
        if type(getattr(CIVote, a)) == \
                sqlalchemy.orm.attributes.InstrumentedAttribute:
            attrs.append(a)
    data['civotes'] = []
    for vote in session.query(CIVote).all():
        d = {}
        for a in attrs:
            d[a] = str(getattr(vote, a))
        data['civotes'].append(d)

    attrs = []
    for a in dir(CIVote_Aggregate):
        if type(getattr(CIVote_Aggregate, a)) == \
                sqlalchemy.orm.attributes.InstrumentedAttribute:
            attrs.append(a)
    data['civotes_agg'] = []
    for vote in session.query(CIVote_Aggregate).all():
        d = {}
        for a in attrs:
            d[a] = str(getattr(vote, a))
        data['civotes_agg'].append(d)

    attrs = []
    for a in dir(User):
        if type(getattr(User, a)) == \
                sqlalchemy.orm.attributes.InstrumentedAttribute:
            attrs.append(a)
    data['users'] = []
    for user in session.query(User).all():
        d = {}
        for a in attrs:
            d[a] = str(getattr(user, a))
        data['users'].append(d)

    attrs = []
    for a in dir(Promotion):
        if type(getattr(Promotion, a)) == \
                sqlalchemy.orm.attributes.InstrumentedAttribute:
            attrs.append(a)
    data['promotions'] = []
    for promotion in session.query(Promotion).all():
        d = {}
        for a in attrs:
            d[a] = str(getattr(promotion, a))
        data['promotions'].append(d)

    with open(yamlfile, 'w') as fp:
        fp.write(yaml.dump(data, default_flow_style=False))


# Save a single commit to yaml
def saveYAML_commit(commit, yamlfile):
    data = {}
    attrs = []
    for a in dir(Commit):
        if type(getattr(Commit, a)) == \
                sqlalchemy.orm.attributes.InstrumentedAttribute:
            attrs.append(a)
    data['commits'] = []
    # Add commit
    d = {}
    for a in attrs:
        d[a] = str(getattr(commit, a))
    data['commits'].append(d)
    with open(yamlfile, 'w') as fp:
        fp.write(yaml.dump(data, default_flow_style=False))


def dumpshas2file(shafile, commit, source_repo, distgit_repo,
                  status, timestamp, component, rpmlist):
    shafile.write("%s,%s,%s,%s,%s,%s,%d,%s,%s,%s\n" % (commit.project_name,
                                                       source_repo,
                                                       commit.commit_hash,
                                                       distgit_repo,
                                                       commit.distro_hash,
                                                       status,
                                                       timestamp,
                                                       component,
                                                       commit.extended_hash,
                                                       getNVRfromlist(rpmlist))
                  )


def getNVRfromlist(rpmlist):
    # Return a string with the source package NVR
    for pkg in rpmlist:
        if pkg.endswith(".src.rpm"):
            return pkg.split('/')[-1].split('.src.rpm')[0]
    return ""


# Check log file against known errors
# Return True if known error, False otherwise
def isknownerror(logfile):

    if not os.path.isfile(logfile):
        return False

    with open(logfile) as fp:
        for line in fp:
            line = line.strip()
            if re_known_errors.search(line):
                # Found a known issue
                return True

    return False


# Return how many times a commit hash / distro had combination has
# been retried for a given project
def timesretried(project, session, commit_hash, distro_hash):
    return session.query(Commit).filter(Commit.project_name == project,
                                        Commit.commit_hash == commit_hash,
                                        Commit.distro_hash == distro_hash,
                                        Commit.status == "RETRY").\
        count()


# Context manager to ensure locking for a file
@contextmanager
def lock_file(filename, mode='a'):
    with open(filename, mode) as lock_fp:
        fcntl.flock(lock_fp, fcntl.LOCK_EX)
        yield lock_fp
        fcntl.flock(lock_fp, fcntl.LOCK_UN)


# Run external pre-processing step
def run_external_preprocess(**kwargs):
    # Initially, get any params to be set as environment variables
    pkgname = kwargs.get('pkgname')
    distgit = kwargs.get('distgit')
    upstream_distgit = kwargs.get('upstream_distgit')
    cmdline = kwargs.get('cmdline')
    distroinfo = kwargs.get('distroinfo')
    srcdir = kwargs.get('source_dir')
    commit_hash = kwargs.get('commit_hash')
    username = os.environ.get('USER', None)
    datadir = kwargs.get('datadir')

    run_cmd = []
    # Append environment variables
    if pkgname:
        run_cmd.append("DLRN_PACKAGE_NAME=%s" % pkgname)
    if distgit:
        run_cmd.append("DLRN_DISTGIT=%s" % distgit)
    if upstream_distgit:
        run_cmd.append("DLRN_UPSTREAM_DISTGIT=%s" % upstream_distgit)
    if distroinfo:
        run_cmd.append("DLRN_DISTROINFO_REPO=%s" % distroinfo)
    if srcdir:
        run_cmd.append("DLRN_SOURCEDIR=%s" % srcdir)
    if commit_hash:
        run_cmd.append("DLRN_SOURCE_COMMIT=%s" % commit_hash)
    if username:
        run_cmd.append("DLRN_USER=%s" % username)
    if datadir:
        run_cmd.append("DLRN_DATADIR=%s" % datadir)
    run_cmd.extend([cmdline])

    logger.info('Running custom pre-process: %s' % ' '.join(run_cmd))
    try:
        # We are forcing LANG to be C here, because env decides to use
        # non-ascii characters when the command is not found in UTF-8
        # environments
        sh.env(run_cmd, _cwd=distgit,
               _env={'LANG': 'C',
                     'MOCK_CONFIG': os.environ.get('MOCK_CONFIG', None),
                     'RELEASE_DATE': os.environ.get('RELEASE_DATE', None),
                     'RELEASE_MINOR': os.environ.get('RELEASE_MINOR', '0'),
                     'RELEASE_NUMBERING': os.environ.get('RELEASE_NUMBERING',
                                                         None)})

    except Exception as e:
        msg = getattr(e, 'stderr', None)
        if msg:
            msg = msg.decode('utf-8')
        else:
            msg = e
        raise RuntimeError('Custom pre-process failed: %s' % msg)


# Return the list of all components that had a package built
def get_component_list(session):
    # The only way we have to get the components is to query the database
    all_comp_commits = session.query(Commit).\
        distinct(Commit.component).group_by(Commit.component).all()
    component_list = []
    for cmt in all_comp_commits:
        if cmt.component is not None:
            component_list.append(cmt.component)
    return component_list


# Aggregate all .repo files from a given symlink into a top-level repo file
# Also, aggregate the versions.csv file, this is useful for additional tooling
def aggregate_repo_files(dirname, datadir, session, reponame,
                         hashed_dir=False):
    component_list = get_component_list(session)

    repo_content = ''
    csv_content = []

    for component in component_list:
        repo_file = os.path.join(datadir, "repos/component", component,
                                 dirname, "%s.repo" % reponame)
        csv_file = os.path.join(datadir, "repos/component", component,
                                dirname, "versions.csv")

        if os.path.exists(repo_file):
            with open(repo_file, 'r') as fp:
                repo_content += fp.read() + '\n'
        if os.path.exists(csv_file):
            with open(csv_file, 'r') as fp:
                csv_content.extend(fp.readlines()[1:])

    file_hash = hashlib.md5(repo_content.encode()).hexdigest()

    if hashed_dir:
        target_dir = os.path.join(datadir, "repos", dirname, file_hash[:2],
                                  file_hash[2:4], file_hash)
    else:
        target_dir = os.path.join(datadir, "repos", dirname)

    # Create target directory if not present
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    with open(os.path.join(target_dir, "%s.repo" % reponame), 'w') as fp:
        fp.write(repo_content)
    with open(os.path.join(target_dir, "%s.repo.md5" % reponame), 'w') as fp:
        fp.write(file_hash)
    with open(os.path.join(target_dir, "versions.csv"), 'w') as fp:
        fp.write("Project,Source Repo,Source Sha,Dist Repo,Dist Sha,"
                 "Status,Last Success Timestamp,Component,Extended Sha,"
                 "Pkg NVR\n")
        fp.writelines(csv_content)

    # If we created the file in a hashed dir, create the symlinks now
    if hashed_dir:
        base_promote_dir = os.path.join(datadir, "repos", dirname)
        os.symlink(os.path.relpath(os.path.join(target_dir,
                                                "%s.repo" % reponame),
                                   base_promote_dir),
                   os.path.join(base_promote_dir, "%s.repo_" % reponame))
        os.rename(os.path.join(base_promote_dir, "%s.repo_" % reponame),
                  os.path.join(base_promote_dir, "%s.repo" % reponame))
        os.symlink(os.path.relpath(os.path.join(target_dir,
                                                "%s.repo.md5" % reponame),
                                   base_promote_dir),
                   os.path.join(base_promote_dir, "%s.repo.md5_" % reponame))
        os.rename(os.path.join(base_promote_dir, "%s.repo.md5_" % reponame),
                  os.path.join(base_promote_dir, "%s.repo.md5" % reponame))
        os.symlink(os.path.relpath(os.path.join(target_dir, 'versions.csv'),
                                   base_promote_dir),
                   os.path.join(base_promote_dir, "versions.csv_"))
        os.rename(os.path.join(base_promote_dir, "versions.csv_"),
                  os.path.join(base_promote_dir, "versions.csv"))

    return file_hash


def find_in_artifacts(artifacts, word):
    if not artifacts:
        return
    for artifact in artifacts.split(','):
        if re.findall(word, artifact):
            return artifact


if __name__ == '__main__':
    s = getSession('sqlite:///%s' % sys.argv[1])
    saveYAML(s, sys.argv[1] + ".yaml")
    s = getSession('sqlite://')
    loadYAML(s, sys.argv[1] + ".yaml")
    print(s.query(Commit).first().project_name)
