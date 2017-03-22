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
import os
import re
import sys
import yaml

import sqlalchemy

from dlrn.db import CIVote
from dlrn.db import Commit
from dlrn.db import getSession
from dlrn.db import Project
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
                             'Temporary failure in name resolution')


# Import a Python object
def import_object(import_str, *args, **kwargs):
    mod_str, _sep, class_str = import_str.rpartition('.')
    __import__(mod_str)
    try:
        myclass = getattr(sys.modules[mod_str], class_str)
        return myclass(*args, **kwargs)
    except AttributeError:
        raise ImportError('Cannot find class %s' % class_str)


# Load a yaml file into a db session, used to populate a in memory database
# during tests
def loadYAML(session, yamlfile):
    with open(yamlfile) as fp:
        data = yaml.load(fp)

    for commit in data['commits']:
        c = Commit(**commit)
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
        for user in data['users']:
            my_user = User(**user)
            session.add(my_user)
            session.commit()
    except KeyError:
        pass   # No users in yaml, just ignore

    session.commit()


# Load a yaml file into a list of commits
def loadYAML_list(yamlfile):
    with open(yamlfile) as fp:
        data = yaml.load(fp)

    commit_list = []
    for commit in data['commits']:
        c = Commit(**commit)
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
                  status, timestamp, rpmlist):
    shafile.write("%s,%s,%s,%s,%s,%s,%d,%s\n" % (commit.project_name,
                                                 source_repo,
                                                 commit.commit_hash,
                                                 distgit_repo,
                                                 commit.distro_hash,
                                                 status,
                                                 timestamp,
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


if __name__ == '__main__':
    s = getSession('sqlite:///%s' % sys.argv[1])
    saveYAML(s, sys.argv[1] + ".yaml")
    s = getSession('sqlite://')
    loadYAML(s, sys.argv[1] + ".yaml")
    print(s.query(Commit).first().project_name)
