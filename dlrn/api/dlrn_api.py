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
from dlrn.api.utils import RepoDetail

from dlrn.db import CIVote
from dlrn.db import Commit
from dlrn.db import getCommits
from dlrn.db import getSession

from dlrn.config import ConfigOptions

from dlrn.remote import import_commit
from dlrn.shell import default_options

from flask import jsonify
from flask import render_template
from flask import request

import os
from six.moves import configparser
from sqlalchemy import desc
import time


@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


def getVote(session, timestamp, success=None, job_id=None, fallback=True):
    votes = session.query(CIVote)
    votes = votes.filter(CIVote.timestamp > timestamp)
    # Initially we want to get any tested repo, excluding consistent repos
    votes = votes.filter(CIVote.ci_name != 'consistent')
    if success is not None:
        votes = votes.filter(CIVote.ci_vote == int(success))
    if job_id is not None:
        votes = votes.filter(CIVote.ci_name == job_id)
    vote = votes.order_by(desc(CIVote.timestamp)).first()

    if vote is None and not fallback:
        # This is the sequential use case. We do not want to find any vote
        # for a different CI
        raise InvalidUsage('No vote found', status_code=404)

    if vote is None and job_id is not None:
        # Second chance: no votes found for job_id. Let's find any real CI
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


@app.route('/api/repo_status', methods=['GET'])
def repo_status():
    # commit_hash: commit hash
    # distro_hash: distro hash
    # success(optional): only report successful/unsuccessful votes
    if request.headers['Content-Type'] != 'application/json':
        raise InvalidUsage('Unsupported Media Type, use JSON', status_code=415)

    commit_hash = request.json.get('commit_hash', None)
    distro_hash = request.json.get('distro_hash', None)
    success = request.json.get('success', None)
    if (commit_hash is None or distro_hash is None):
        raise InvalidUsage('Missing parameters', status_code=400)

    if success is not None:
        success = bool(strtobool(success))

    # Find the commit id for commit_hash/distro_hash
    session = getSession(app.config['DB_PATH'])
    commit = session.query(Commit).filter(
        Commit.status == 'SUCCESS',
        Commit.commit_hash == commit_hash,
        Commit.distro_hash == distro_hash).first()
    if commit is None:
        raise InvalidUsage('commit_hash+distro_hash combination not found',
                           status_code=404)
    commit_id = commit.id

    # Now find every vote for this commit_hash/distro_hash combination
    votes = session.query(CIVote).filter(CIVote.commit_id == commit_id)
    if success is not None:
        votes = votes.filter(CIVote.ci_vote == int(success))

    # And format the output
    data = []
    for vote in votes:
        d = {'timestamp': vote.timestamp,
             'commit_hash': commit_hash,
             'distro_hash': distro_hash,
             'job_id': vote.ci_name,
             'success': bool(vote.ci_vote),
             'in_progress': vote.ci_in_progress,
             'url': vote.ci_url,
             'notes': vote.notes}
        data.append(d)
    session.close()
    return jsonify(data)


@app.route('/api/last_tested_repo', methods=['GET'])
def last_tested_repo_GET():
    # max_age: Maximum age in hours, used as base for the search
    # success(optional): find repos with a successful/unsuccessful vote
    # job_id(optional); name of the CI that sent the vote
    # sequential_mode(optional): if set to true, change the search algorithm
    #                            to only use previous_job_id as CI name to
    #                            search for. Defaults to false
    # previous_job_id(optional): CI name to search for, if sequential_mode is
    #                            True
    if request.headers['Content-Type'] != 'application/json':
        raise InvalidUsage('Unsupported Media Type, use JSON', status_code=415)

    max_age = request.json.get('max_age', None)
    job_id = request.json.get('job_id', None)
    success = request.json.get('success', None)
    sequential_mode = request.json.get('sequential_mode', None)
    previous_job_id = request.json.get('previous_job_id', None)

    if success is not None:
        success = bool(strtobool(success))

    if sequential_mode is not None:
        sequential_mode = bool(strtobool(sequential_mode))

    if sequential_mode and previous_job_id is None:
        raise InvalidUsage('Missing parameter previous_job_id',
                           status_code=400)

    if max_age is None:
        raise InvalidUsage('Missing parameters', status_code=400)

    # Calculate timestamp as now - max_age
    if int(max_age) == 0:
        timestamp = 0
    else:
        oldest_time = datetime.now() - timedelta(hours=int(max_age))
        timestamp = time.mktime(oldest_time.timetuple())

    session = getSession(app.config['DB_PATH'])
    try:
        if sequential_mode:
            # CI pipeline case
            vote = getVote(session, timestamp, success, previous_job_id,
                           fallback=False)
        else:
            # Normal case
            vote = getVote(session, timestamp, success, job_id)
    except Exception as e:
        raise e

    commit = session.query(Commit).filter(
        Commit.status == 'SUCCESS',
        Commit.id == vote.commit_id).first()

    result = {'commit_hash': commit.commit_hash,
              'distro_hash': commit.distro_hash,
              'timestamp': vote.timestamp,
              'job_id': vote.ci_name,
              'success': vote.ci_vote,
              'in_progress': vote.ci_in_progress}
    session.close()
    return jsonify(result), 200


@app.route('/api/last_tested_repo', methods=['POST'])
@auth.login_required
def last_tested_repo_POST():
    # max_age: Maximum age in hours, used as base for the search
    # success(optional): find repos with a successful/unsuccessful vote
    # job_id(optional); name of the CI that sent the vote
    # reporting_job_id: name of the CI that will test this repo
    # sequential_mode(optional): if set to true, change the search algorithm
    #                            to only use previous_job_id as CI name to
    #                            search for. Defaults to false
    # previous_job_id(optional): CI name to search for, if sequential_mode is
    #                            True
    if request.headers['Content-Type'] != 'application/json':
        raise InvalidUsage('Unsupported Media Type, use JSON', status_code=415)

    max_age = request.json.get('max_age', None)
    my_job_id = request.json.get('reporting_job_id', None)
    job_id = request.json.get('job_id', None)
    success = request.json.get('success', None)
    sequential_mode = request.json.get('sequential_mode', None)
    previous_job_id = request.json.get('previous_job_id', None)

    if success is not None:
        success = bool(strtobool(success))

    if sequential_mode is not None:
        sequential_mode = bool(strtobool(sequential_mode))

    if sequential_mode and previous_job_id is None:
        raise InvalidUsage('Missing parameter previous_job_id',
                           status_code=400)

    if (max_age is None or my_job_id is None):
        raise InvalidUsage('Missing parameters', status_code=400)

    # Calculate timestamp as now - max_age
    if int(max_age) == 0:
        timestamp = 0
    else:
        oldest_time = datetime.now() - timedelta(hours=int(max_age))
        timestamp = time.mktime(oldest_time.timetuple())

    session = getSession(app.config['DB_PATH'])

    try:
        if sequential_mode:
            # CI pipeline case
            vote = getVote(session, timestamp, success, previous_job_id,
                           fallback=False)
        else:
            # Normal case
            vote = getVote(session, timestamp, success, job_id)
    except Exception as e:
        raise e

    newvote = CIVote(commit_id=vote.commit_id, ci_name=my_job_id,
                     ci_url='', ci_vote=False, ci_in_progress=True,
                     timestamp=int(time.time()), notes='')
    session.add(newvote)
    session.commit()

    commit = session.query(Commit).filter(
        Commit.status == 'SUCCESS',
        Commit.id == vote.commit_id).first()

    result = {'commit_hash': commit.commit_hash,
              'distro_hash': commit.distro_hash,
              'timestamp': newvote.timestamp,
              'job_id': newvote.ci_name,
              'success': newvote.ci_vote,
              'in_progress': newvote.ci_in_progress}
    session.close()
    return jsonify(result), 201


@app.route('/api/report_result', methods=['POST'])
@auth.login_required
def report_result():
    # job_id: name of CI
    # commit_hash: commit hash
    # distro_hash: distro hash
    # url: URL where more information can be found
    # timestamp: CI execution timestamp
    # success: boolean
    # notes(optional): notes

    if request.headers['Content-Type'] != 'application/json':
        raise InvalidUsage('Unsupported Media Type, use JSON', status_code=415)

    try:
        commit_hash = request.json['commit_hash']
        distro_hash = request.json['distro_hash']
        timestamp = request.json['timestamp']
        job_id = request.json['job_id']
        success = request.json['success']
        url = request.json['url']
    except KeyError:
        raise InvalidUsage('Missing parameters', status_code=400)

    notes = request.json.get('notes', '')

    session = getSession(app.config['DB_PATH'])
    commit = session.query(Commit).filter(
        Commit.status == 'SUCCESS',
        Commit.commit_hash == commit_hash,
        Commit.distro_hash == distro_hash).first()
    if commit is None:
        raise InvalidUsage('commit_hash+distro_hash combination not found',
                           status_code=404)

    commit_id = commit.id

    vote = CIVote(commit_id=commit_id, ci_name=job_id, ci_url=url,
                  ci_vote=bool(strtobool(success)), ci_in_progress=False,
                  timestamp=int(timestamp), notes=notes)
    session.add(vote)
    session.commit()

    result = {'commit_hash': commit_hash,
              'distro_hash': distro_hash,
              'timestamp': timestamp,
              'job_id': job_id,
              'success': bool(success),
              'in_progress': False,
              'url': url,
              'notes': notes}
    session.close()
    return jsonify(result), 201


@app.route('/api/promote', methods=['POST'])
@auth.login_required
def promote():
    # commit_hash: commit hash
    # distro_hash: distro hash
    # promote_name: symlink name

    if request.headers['Content-Type'] != 'application/json':
        raise InvalidUsage('Unsupported Media Type, use JSON', status_code=415)

    try:
        commit_hash = request.json['commit_hash']
        distro_hash = request.json['distro_hash']
        promote_name = request.json['promote_name']
    except KeyError:
        raise InvalidUsage('Missing parameters', status_code=400)

    # Check for invalid promote names
    if (promote_name == 'consistent' or promote_name == 'current'):
        raise InvalidUsage('Invalid promote_name %s' % promote_name,
                           status_code=403)

    session = getSession(app.config['DB_PATH'])
    commit = session.query(Commit).filter(
        Commit.status == 'SUCCESS',
        Commit.commit_hash == commit_hash,
        Commit.distro_hash == distro_hash).first()
    if commit is None:
        raise InvalidUsage('commit_hash+distro_hash combination not found',
                           status_code=404)

    target_link = os.path.join(app.config['REPO_PATH'], promote_name)
    # Check for invalid target links, like ../promotename
    target_dir = os.path.dirname(os.path.abspath(target_link))
    if not os.path.samefile(target_dir, app.config['REPO_PATH']):
        raise InvalidUsage('Invalid promote_name %s' % promote_name,
                           status_code=403)

    # We should create a relative symlink
    yumrepodir = commit.getshardedcommitdir()

    # Remove symlink if it exists, so we can create it again
    if os.path.lexists(os.path.abspath(target_link)):
        os.remove(target_link)
    try:
        os.symlink(yumrepodir, target_link)
    except Exception as e:
        raise InvalidUsage("Symlink creation failed with error: %s" %
                           e, status_code=500)

    result = {'commit_hash': commit_hash,
              'distro_hash': distro_hash,
              'promote_name': promote_name}
    session.close()
    return jsonify(result), 201


@app.route('/api/remote/import', methods=['POST'])
@auth.login_required
def remote_import():
    # repo_url: repository URL to import from
    if request.headers['Content-Type'] != 'application/json':
        raise InvalidUsage('Unsupported Media Type, use JSON', status_code=415)

    try:
        repo_url = request.json['repo_url']
    except KeyError:
        raise InvalidUsage('Missing parameters', status_code=400)

    try:
        import_commit(repo_url, app.config['CONFIG_FILE'],
                      db_connection=app.config['DB_PATH'])
    except Exception as e:
        raise InvalidUsage("Remote import failed with error: %s" %
                           e, status_code=500)

    result = {'repo_url': repo_url}
    return jsonify(result), 201


@app.template_filter()
def strftime(date, fmt="%Y-%m-%d %H:%M:%S"):
    gmdate = time.gmtime(date)
    return "%s" % time.strftime(fmt, gmdate)


@app.route('/api/civotes.html', methods=['GET'])
def get_civotes():
    session = getSession(app.config['DB_PATH'])
    votes = session.query(CIVote)
    votes = votes.filter(CIVote.ci_name != 'consistent')

    # Let's find all individual commit_hash + distro_hash combinations
    commit_id_list = []
    for vote in votes:
        if vote.commit_id not in commit_id_list:
            commit_id_list.append(vote.commit_id)

    # Populate list for commits
    repolist = []
    for commit_id in commit_id_list:
        commit = getCommits(session, limit=0).filter(
            Commit.id == commit_id).first()

        repodetail = RepoDetail()
        repodetail.commit_hash = commit.commit_hash
        repodetail.distro_hash = commit.distro_hash
        repodetail.distro_hash_short = commit.distro_hash[:8]
        repodetail.success = votes.filter(CIVote.commit_id == commit_id,
                                          CIVote.ci_vote == 1).count()
        repodetail.failure = votes.filter(CIVote.commit_id == commit_id,
                                          CIVote.ci_vote == 0).count()
        repodetail.timestamp = votes.filter(CIVote.commit_id == commit_id).\
            order_by(desc(CIVote.timestamp)).first().timestamp
        repolist.append(repodetail)

    repolist = sorted(repolist, key=lambda repo: repo.timestamp, reverse=True)
    session.close()
    return render_template('votes_general.j2',
                           target='master',
                           repodetail=repolist)


@app.route('/api/civotes_detail.html', methods=['GET'])
def get_civotes_detail():
    commit_hash = request.args.get('commit_hash', None)
    distro_hash = request.args.get('distro_hash', None)
    success = request.args.get('success', None)

    session = getSession(app.config['DB_PATH'])
    votes = session.query(CIVote)
    votes = votes.filter(CIVote.ci_name != 'consistent')

    if commit_hash and distro_hash:
        commit = session.query(Commit).filter(
            Commit.status == 'SUCCESS',
            Commit.commit_hash == commit_hash,
            Commit.distro_hash == distro_hash).first()
        votes = votes.filter(CIVote.commit_id == commit.id)
    else:
        raise InvalidUsage("Please specify commit_hash and distro_hash as "
                           "parameters", status_code=400)

    if success is not None:
        votes = votes.filter(CIVote.ci_vote == bool(strtobool(success)))

    votelist = votes.all()

    for i in range(len(votelist)):
        commit = getCommits(session, limit=0).filter(
            Commit.id == votelist[i].commit_id).first()
        votelist[i].commit_hash = commit.commit_hash
        votelist[i].distro_hash = commit.distro_hash
        votelist[i].distro_hash_short = commit.distro_hash[:8]
    session.close()
    return render_template('votes.j2',
                           target='master',
                           votes=votelist)


@app.route('/api/report.html', methods=['GET'])
def get_report():
    package_name = request.args.get('package', None)
    success = request.args.get('success', None)

    if success is not None:
        if bool(strtobool(success)):
            with_status = "SUCCESS"
        else:
            with_status = "FAILED"
    else:
        with_status = None

    session = getSession(app.config['DB_PATH'])
    commits = getCommits(session, without_status="RETRY",
                         project=package_name, with_status=with_status,
                         limit=1000)

    cp = configparser.RawConfigParser(default_options)
    cp.read(app.config['CONFIG_FILE'])
    config_options = ConfigOptions(cp)

    return render_template('report.j2',
                           reponame='Detailed build report',
                           target=config_options.target,
                           src=config_options.source,
                           commits=commits)
