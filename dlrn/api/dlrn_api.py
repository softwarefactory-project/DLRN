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

from datetime import datetime
from datetime import timedelta
from distutils.util import strtobool

from dlrn.api import app
from dlrn.api.utils import auth
from dlrn.api.utils import InvalidUsage

from dlrn.db import CIVote
from dlrn.db import Commit
from dlrn.db import getCommits
from dlrn.db import getSession

from flask import jsonify
from flask import render_template
from flask import request

import os
import sqlalchemy
from sqlalchemy import desc
from sqlalchemy import distinct
import time


@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


def getVote(session, timestamp, success=None, link_name=None):
    votes = session.query(CIVote)
    votes = votes.filter(CIVote.timestamp > timestamp)
    # Initially we want to get any tested repo, excluding consistent repos
    votes = votes.filter(CIVote.ci_name != 'consistent')
    if success is not None:
        votes = votes.filter(CIVote.ci_vote == int(success))
    if link_name is not None:
        votes = votes.filter(CIVote.ci_name == link_name)
    vote = votes.order_by(desc(CIVote.timestamp)).first()

    if vote is None and link_name is not None:
        # Second chance: no votes found for link_name. Let's find any real CI
        # vote, other than 'consistent'
        votes = session.query(CIVote).filter(CIVote.timestamp >
                                             timestamp)
        if success is not None:
            votes = votes.filter(CIVote.ci_vote == success)
        votes.filter(CIVote.ci_name != 'consistent')
        vote = votes.order_by(desc(CIVote.timestamp)).first()

    if vote is None:
        # No votes found, let's try to find one for consistent
        votes = session.query(CIVote).filter(CIVote.timestamp >
                                             timestamp)
        if success is not None:
            votes = votes.filter(CIVote.ci_vote == success)
        votes.filter(CIVote.ci_name == 'consistent')
        vote = votes.order_by(desc(CIVote.timestamp)).first()

    if vote is None:
        # No Votes found at all
        raise InvalidUsage('No vote found', status_code=404)

    return vote


@app.route('/api/last_tested_repo', methods=['GET'])
def last_tested_repo_GET():
    # timestamp: Timestamp in secs since the epoch used as base for the search
    # success(optional): find repos with a successful/unsuccessful vote
    # link_name(optional); name of the CI that sent the vote
    if request.headers['Content-Type'] != 'application/json':
        raise InvalidUsage('Unsupported Media Type, use JSON', status_code=415)

    max_age = request.json.get('max_age', None)
    link_name = request.json.get('link_name', None)
    success = request.json.get('success', None)

    if success is not None:
        success = bool(strtobool(success))

    if max_age is None:
        raise InvalidUsage('Missing parameters', status_code=400)

    # Calculate timestamp as now - max_age
    if int(max_age) == 0:
        timestamp = 0
    else:
        oldest_time = datetime.now() - timedelta(days=int(max_age))
        timestamp = time.mktime(oldest_time.timetuple())

    session = getSession(app.config['DB_PATH'])
    try:
        vote = getVote(session, timestamp, success, link_name)
    except Exception as e:
        raise e

    commit = session.query(Commit).filter(
        Commit.id == vote.commit_id).first()

    result = {'commit_hash': commit.commit_hash,
              'distro_hash': commit.distro_hash,
              'timestamp': vote.timestamp,
              'link_name': vote.ci_name,
              'success': vote.ci_vote,
              'in_progress': vote.ci_in_progress}
    return jsonify(result), 200


@app.route('/api/last_tested_repo', methods=['POST'])
@auth.login_required
def last_tested_repo_POST():
    # timestamp: Timestamp in secs since the epoch used as base for the search
    # success(optional): find repos with a successful/unsuccessful vote
    # link_name(optional); name of the CI that sent the vote
    if request.headers['Content-Type'] != 'application/json':
        raise InvalidUsage('Unsupported Media Type, use JSON', status_code=415)

    max_age = request.json.get('max_age', None)
    my_link_name = request.json.get('reporting_link_name', None)
    link_name = request.json.get('link_name', None)
    success = request.json.get('success', None)

    if success is not None:
        success = bool(strtobool(success))

    if (max_age is None or my_link_name is None):
        raise InvalidUsage('Missing parameters', status_code=400)

    # Calculate timestamp as now - max_age
    if int(max_age) == 0:
        timestamp = 0
    else:
        oldest_time = datetime.now() - timedelta(days=int(max_age))
        timestamp = time.mktime(oldest_time.timetuple())

    session = getSession(app.config['DB_PATH'])

    try:
        vote = getVote(session, timestamp, success, link_name)
    except Exception as e:
        raise e

    newvote = CIVote(commit_id=vote.commit_id, ci_name=my_link_name,
                     ci_url='', ci_vote=False, ci_in_progress=True,
                     timestamp=int(time.time()), notes='')
    session.add(newvote)
    session.commit()

    commit = session.query(Commit).filter(
        Commit.id == vote.commit_id).first()

    result = {'commit_hash': commit.commit_hash,
              'distro_hash': commit.distro_hash,
              'timestamp': newvote.timestamp,
              'link_name': newvote.ci_name,
              'success': newvote.ci_vote,
              'in_progress': newvote.ci_in_progress}
    return jsonify(result), 201


@app.route('/api/report_result', methods=['POST'])
@auth.login_required
def report_result():
    # link_name: name of CI
    # success: boolean
    # url: URL where more information can be found
    # commit_hash: commit hash
    # distro_hash: distro hash
    # timestamp: CI execution timestamp
    # create_symlink: create symlink to repo (optional, false by default)
    # notes(optional): notes

    if request.headers['Content-Type'] != 'application/json':
        raise InvalidUsage('Unsupported Media Type, use JSON', status_code=415)

    try:
        commit_hash = request.json['commit_hash']
        distro_hash = request.json['distro_hash']
        timestamp = request.json['timestamp']
        link_name = request.json['link_name']
        success = request.json['success']
        url = request.json['url']
    except KeyError:
        raise InvalidUsage('Missing parameters', status_code=400)

    notes = request.json.get('notes', '')
    create_symlink = bool(strtobool(request.json.get('create_symlink', False)))

    session = getSession(app.config['DB_PATH'])
    commit = session.query(Commit).filter(
        Commit.commit_hash == commit_hash,
        Commit.distro_hash == distro_hash).first()
    if commit is None:
        raise InvalidUsage('commit_hash+distro_hash combination not found',
                           status_code=404)

    commit_id = commit.id

    vote = CIVote(commit_id=commit_id, ci_name=link_name, ci_url=url,
                  ci_vote=bool(strtobool(success)), ci_in_progress=False,
                  timestamp=int(timestamp), notes=notes)
    session.add(vote)
    session.commit()

    if create_symlink:
        target_link = os.path.join(app.config['REPO_PATH'], link_name)
        yumrepodir = os.path.join(app.config['REPO_PATH'],
                                  commit.getshardedcommitdir())
        try:
            os.symlink(yumrepodir, target_link)
        except Exception as e:
            raise InvalidUsage("Symlink creation failed with error: %s" %
                               e, status_code=500)

    result = {'commit_hash': commit_hash,
              'distro_hash': distro_hash,
              'timestamp': timestamp,
              'link_name': link_name,
              'success': success,
              'in_progress': False,
              'url': url,
              'create_symlink': create_symlink,
              'notes': notes}
    return jsonify(result), 201


# Everything below this line is just tests
@app.template_filter()
def strftime(date, fmt="%Y-%m-%d %H:%M:%S"):
    gmdate = time.gmtime(date)
    return "%s" % time.strftime(fmt, gmdate)


@app.route('/api/commits', methods=['GET'])
def get_commits():
    session = getSession(app.config['DB_PATH'])
    commits = getCommits(session, limit=0).all()

    data = {}
    attrs = []
    for a in dir(Commit):
        if type(getattr(Commit, a)) == \
                sqlalchemy.orm.attributes.InstrumentedAttribute:
            attrs.append(a)
    data['commits'] = []
    for commit in commits:
        d = {}
        for a in attrs:
            d[a] = str(getattr(commit, a))
        data['commits'].append(d)
    return jsonify(data)


@app.route('/api/commits.html', methods=['GET'])
def get_commits_html():
    session = getSession(app.config['DB_PATH'])
    commits = getCommits(session, limit=0).all()
    return render_template('report.j2',
                           commits=commits,
                           reponame="Test repo",
                           target="Centos",
                           src='kk')


@app.route('/api/failed_commits.html', methods=['GET'])
def get_failed_commits_html():
    session = getSession(app.config['DB_PATH'])
    package_list = session.query(distinct(Commit.project_name)).all()
    commits = []
    for package in package_list:
        pkgname = package[0]
        commit = getCommits(session, project=pkgname, limit=1).first()
        if commit.status == 'FAILED':  # should be FAILED
            commits.append(commit)

    return render_template('report_failed.j2',
                           commits=commits,
                           reponame="Failed commits for repo",
                           target="Centos",
                           src='kk')


@app.route('/api/recheck_commit', methods=['POST'])
@auth.login_required
def recheck_commit():
    return "Rechecked commit for %s" % request.args['project_name']
