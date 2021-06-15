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
from functools import wraps

from dlrn.api import app
from dlrn.api.utils import AggDetail
from dlrn.api.utils import auth
from dlrn.api.utils import InvalidUsage
from dlrn.api.utils import RepoDetail

from dlrn.config import ConfigOptions
from dlrn.db import CIVote
from dlrn.db import CIVote_Aggregate
from dlrn.db import closeSession
from dlrn.db import Commit
from dlrn.db import getCommits
from dlrn.db import getSession
from dlrn.db import Promotion
from dlrn.purge import FLAG_PURGED
from dlrn.remote import import_commit
from dlrn.utils import aggregate_repo_files

from flask import g as flask_g
from flask import jsonify
from flask import render_template
from flask import request

import calendar
import os
from six.moves import configparser
from sqlalchemy import desc
import time


pagination_limit = 100
max_limit = 100


def _get_db():
    if 'db' not in flask_g:
        flask_g.db = getSession(app.config['DB_PATH'])
    return flask_g.db


def _get_config_options(config_file):
    cp = configparser.RawConfigParser()
    cp.read(config_file)
    return ConfigOptions(cp)


def _repo_hash(commit):
    return "%s_%s" % (commit.commit_hash, commit.distro_hash[:8])


def _json_media_type(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('Content-Type') != 'application/json':
            raise InvalidUsage('Unsupported Media Type, use JSON',
                               status_code=415)
        return f(*args, **kwargs)
    return decorated_function


def _get_commit(session, commit_hash, distro_hash, extended_hash=None):
    commit = session.query(Commit).filter(
        Commit.status == 'SUCCESS',
        Commit.commit_hash == commit_hash,
        Commit.distro_hash == distro_hash)
    # If an extended hash is specified, also filter for it. Since it
    # could be None, we are falling back to the previous behavior for
    # compatibility
    if extended_hash:
        commit = commit.filter(Commit.extended_hash == extended_hash)
    commit = commit.order_by(desc(Commit.id)).first()
    return commit


def _rollback_batch_promotion(rollback_list):
    # We want to roll everything back in reverse order
    # We will try our best, but there is never a 100% guarantee
    for item in reversed(rollback_list):
        target_link = item['target_link']
        previous_link = item['previous_link']
        # Remove new link
        try:
            os.remove(target_link)
        except Exception:
            pass    # yes, ignore errors
        # Re-establish old link, if it existed
        if previous_link:
            try:
                os.symlink(previous_link, target_link)
            except Exception:
                pass    # yes, ignore errors


@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


def getVote(session, timestamp, success=None, job_id=None, component=None,
            fallback=True):
    votes = session.query(CIVote)
    votes = votes.filter(CIVote.timestamp > timestamp)
    # Initially we want to get any tested repo, excluding consistent repos
    votes = votes.filter(CIVote.ci_name != 'consistent')
    if success is not None:
        votes = votes.filter(CIVote.ci_vote == int(success))
    if job_id is not None:
        votes = votes.filter(CIVote.ci_name == job_id)
    if component is not None:
        votes = votes.filter(CIVote.component == component)
    vote = votes.order_by(desc(CIVote.timestamp)).first()

    if vote is None and not fallback:
        # This is the sequential use case. We do not want to find any vote
        # for a different CI
        raise InvalidUsage('No vote found', status_code=400)

    if vote is None and job_id is not None:
        # Second chance: no votes found for job_id. Let's find any real CI
        # vote, other than 'consistent'
        votes = session.query(CIVote).filter(CIVote.timestamp > timestamp)
        if success is not None:
            votes = votes.filter(CIVote.ci_vote == success)
        votes.filter(CIVote.ci_name != 'consistent')
        vote = votes.order_by(desc(CIVote.timestamp)).first()

    if vote is None:
        # No votes found, let's try to find one for consistent
        votes = session.query(CIVote).filter(CIVote.timestamp > timestamp)
        if success is not None:
            votes = votes.filter(CIVote.ci_vote == success)
        if component is not None:
            votes = votes.filter(CIVote.component == component)
        votes.filter(CIVote.ci_name == 'consistent')
        vote = votes.order_by(desc(CIVote.timestamp)).first()

    if vote is None:
        # No Votes found at all
        raise InvalidUsage('No vote found', status_code=400)

    return vote


@app.route('/api/health', methods=['GET'])
def health():
    # Check database connection
    session = _get_db()
    commit = session.query(Commit).first()
    if commit:
        result = {'result': 'ok'}
    else:
        result = {'result': 'ok, no commits in DB'}
    return jsonify(result), 200


@app.route('/api/health', methods=['POST'])
@auth.login_required
def health_post():
    # Check database connection
    session = _get_db()
    commit = session.query(Commit).first()
    if commit:
        result = {'result': 'ok'}
    else:
        result = {'result': 'ok, no commits in DB'}
    return jsonify(result), 200


@app.route('/api/repo_status', methods=['GET'])
def repo_status():
    # commit_hash: commit hash
    # distro_hash: distro hash
    # extended_hash(optional): extended hash
    # success(optional): only report successful/unsuccessful votes

    commit_hash = request.args.get('commit_hash', None)
    distro_hash = request.args.get('distro_hash', None)
    extended_hash = request.args.get('extended_hash', None)
    success = request.args.get('success', None)

    if request.headers.get('Content-Type') == 'application/json':
        # This is the old, deprecated method of in-body parameters
        # We will keep it for backwards compatibility
        if commit_hash is None:
            commit_hash = request.json.get('commit_hash', None)
        if distro_hash is None:
            distro_hash = request.json.get('distro_hash', None)
        if extended_hash is None:
            extended_hash = request.json.get('extended_hash', None)
        if success is None:
            success = request.json.get('success', None)

    if (commit_hash is None or distro_hash is None):
        raise InvalidUsage('Missing parameters', status_code=400)

    if success is not None:
        success = bool(strtobool(success))

    # Find the commit id for commit_hash/distro_hash
    session = _get_db()
    commit = _get_commit(session, commit_hash, distro_hash, extended_hash)

    if commit is None:
        raise InvalidUsage('commit_hash+distro_hash+extended_hash combination'
                           ' not found', status_code=400)
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
             'extended_hash': commit.extended_hash,
             'job_id': vote.ci_name,
             'success': bool(vote.ci_vote),
             'in_progress': vote.ci_in_progress,
             'url': vote.ci_url,
             'notes': vote.notes,
             'user': vote.user,
             'component': vote.component}
        data.append(d)
    return jsonify(data)


@app.route('/api/agg_status', methods=['GET'])
def agg_status():
    # aggregate_hash: aggregate hash
    # success(optional): only report successful/unsuccessful votes
    agg_hash = request.args.get('aggregate_hash', None)
    success = request.args.get('success', None)

    if request.headers.get('Content-Type') == 'application/json':
        # This is the old, deprecated method of in-body parameters
        # We will keep it for backwards compatibility
        if agg_hash is None:
            agg_hash = request.json.get('aggregate_hash', None)
        if success is None:
            success = request.json.get('success', None)

    if agg_hash is None:
        raise InvalidUsage('Missing parameters', status_code=400)

    if success is not None:
        success = bool(strtobool(success))

    # Find the aggregates
    session = _get_db()
    votes = session.query(CIVote_Aggregate)
    votes = votes.filter(CIVote_Aggregate.ref_hash == agg_hash)
    if success is not None:
        votes = votes.filter(CIVote_Aggregate.ci_vote == int(success))

    # And format the output
    data = []
    for vote in votes:
        d = {'timestamp': vote.timestamp,
             'aggregate_hash': agg_hash,
             'job_id': vote.ci_name,
             'success': bool(vote.ci_vote),
             'in_progress': vote.ci_in_progress,
             'url': vote.ci_url,
             'notes': vote.notes,
             'user': vote.user}
        data.append(d)
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
    # component(optional): only get votes for this component

    max_age = request.args.get('max_age', None)
    job_id = request.args.get('job_id', None)
    success = request.args.get('success', None)
    sequential_mode = request.args.get('sequential_mode', None)
    previous_job_id = request.args.get('previous_job_id', None)
    component = request.args.get('component', None)

    if request.headers.get('Content-Type') == 'application/json':
        # This is the old, deprecated method of in-body parameters
        # We will keep it for backwards compatibility
        if max_age is None:
            max_age = request.json.get('max_age', None)
        if job_id is None:
            job_id = request.json.get('job_id', None)
        if success is None:
            success = request.json.get('success', None)
        if sequential_mode is None:
            sequential_mode = request.json.get('sequential_mode', None)
        if previous_job_id is None:
            previous_job_id = request.json.get('previous_job_id', None)
        if component is None:
            component = request.json.get('component', None)

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

    session = _get_db()
    try:
        if sequential_mode:
            # CI pipeline case
            vote = getVote(session, timestamp, success, previous_job_id,
                           component=component, fallback=False)
        else:
            # Normal case
            vote = getVote(session, timestamp, success, job_id,
                           component=component)
    except Exception as e:
        raise e

    commit = session.query(Commit).filter(
        Commit.status == 'SUCCESS',
        Commit.id == vote.commit_id).first()

    result = {'commit_hash': commit.commit_hash,
              'distro_hash': commit.distro_hash,
              'extended_hash': commit.extended_hash,
              'timestamp': vote.timestamp,
              'job_id': vote.ci_name,
              'success': vote.ci_vote,
              'in_progress': vote.ci_in_progress,
              'user': vote.user,
              'component': vote.component}
    return jsonify(result), 200


@app.route('/api/promotions', methods=['GET'])
def promotions_GET():
    # commit_hash(optional): commit hash
    # distro_hash(optional): distro hash
    # extended_hash(optional): extended hash
    # aggregate_hash(optional): aggregate hash
    # promote_name(optional): only report promotions for promote_name
    # offset(optional): skip the first X promotions (only 100 are shown
    #                   per query)
    # limit(optional): maximum number of entries to return
    # component(optional): only report promotions for this component
    commit_hash = request.args.get('commit_hash', None)
    distro_hash = request.args.get('distro_hash', None)
    extended_hash = request.args.get('extended_hash', None)
    agg_hash = request.args.get('aggregate_hash', None)
    promote_name = request.args.get('promote_name', None)
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 100))
    component = request.args.get('component', None)

    if request.headers.get('Content-Type') == 'application/json':
        # This is the old, deprecated method of in-body parameters
        # We will keep it for backwards compatibility
        if commit_hash is None:
            commit_hash = request.json.get('commit_hash', None)
        if distro_hash is None:
            distro_hash = request.json.get('distro_hash', None)
        if extended_hash is None:
            extended_hash = request.json.get('extended_hash', None)
        if agg_hash is None:
            agg_hash = request.json.get('aggregate_hash', None)
        if promote_name is None:
            promote_name = request.json.get('promote_name', None)
        if offset == 0:
            offset = int(request.json.get('offset', 0))
        if limit == 100:
            limit = int(request.json.get('limit', 100))
        if component is None:
            component = request.json.get('component', None)

    config_options = _get_config_options(app.config['CONFIG_FILE'])

    # Make sure we do not exceed
    if limit > max_limit:
        limit = max_limit

    if ((commit_hash and not distro_hash) or
            (distro_hash and not commit_hash)):

        raise InvalidUsage('Both commit_hash and distro_hash must be '
                           'specified if any of them is.',
                           status_code=400)

    # Find the commit id for commit_hash/distro_hash
    session = _get_db()
    if commit_hash and distro_hash:
        commit = _get_commit(session, commit_hash, distro_hash, extended_hash)
        if commit is None:
            raise InvalidUsage('commit_hash+distro_hash+extended_hash '
                               'combination not found', status_code=400)
        commit_id = commit.id
    else:
        commit_id = None

    # Now find the promotions, and filter if necessary
    promotions = session.query(Promotion)
    if commit_id is not None:
        promotions = promotions.filter(Promotion.commit_id == commit_id)
    if promote_name is not None:
        promotions = promotions.filter(
            Promotion.promotion_name == promote_name)
    if agg_hash is not None:
        promotions = promotions.filter(Promotion.aggregate_hash == agg_hash)
    if component is not None:
        promotions = promotions.filter(Promotion.component == component)

    promotions = promotions.order_by(desc(Promotion.id)).limit(limit).\
        offset(offset)

    # And format the output
    data = []
    for promotion in promotions:
        commit = getCommits(session, limit=0).filter(
            Commit.id == promotion.commit_id).first()

        repo_hash = _repo_hash(commit)
        repo_url = "%s/%s" % (config_options.baseurl,
                              commit.getshardedcommitdir())

        d = {'timestamp': promotion.timestamp,
             'commit_hash': commit.commit_hash,
             'distro_hash': commit.distro_hash,
             'extended_hash': commit.extended_hash,
             'aggregate_hash': promotion.aggregate_hash,
             'repo_hash': repo_hash,
             'repo_url': repo_url,
             'promote_name': promotion.promotion_name,
             'component': promotion.component,
             'user': promotion.user}
        data.append(d)
    return jsonify(data)


@app.route('/api/metrics/builds', methods=['GET'])
def get_metrics():
    # start_date: start date for period, in YYYY-mm-dd format (UTC)
    # end_date: end date for period, in YYYY-mm-dd format (UTC)
    # package_name (optional): return metrics for package_name
    start_date = request.args.get('start_date', None)
    end_date = request.args.get('end_date', None)
    package_name = request.args.get('package_name', None)

    if request.headers.get('Content-Type') == 'application/json':
        # This is the old, deprecated method of in-body parameters
        # We will keep it for backwards compatibility
        if start_date is None:
            start_date = request.json.get('start_date', None)
        if end_date is None:
            end_date = request.json.get('end_date', None)
        if package_name is None:
            package_name = request.json.get('package_name', None)

    if start_date is None or end_date is None:
        raise InvalidUsage('Missing parameters', status_code=400)

    # Convert dates to timestamp
    fmt = '%Y-%m-%d'
    try:
        start_timestamp = int(calendar.timegm(time.strptime(start_date, fmt)))
        end_timestamp = int(calendar.timegm(time.strptime(end_date, fmt)))
    except ValueError:
        raise InvalidUsage('Invalid date format, it must be YYYY-mm-dd',
                           status_code=400)

    # Find the commits count for each metric
    session = _get_db()
    commits = session.query(Commit).filter(
        Commit.status == 'SUCCESS',
        Commit.dt_build >= start_timestamp,
        Commit.dt_build < end_timestamp)

    if package_name:
        commits = commits.filter(
            Commit.project_name == package_name)

    successful_commits = commits.count()

    commits = session.query(Commit).filter(
        Commit.status == 'FAILED',
        Commit.dt_build >= start_timestamp,
        Commit.dt_build <= end_timestamp)

    if package_name:
        commits = commits.filter(
            Commit.project_name == package_name)

    failed_commits = commits.count()
    total_commits = successful_commits + failed_commits

    result = {'succeeded': successful_commits,
              'failed': failed_commits,
              'total': total_commits}
    return jsonify(result), 200


@app.route('/api/last_tested_repo', methods=['POST'])
@auth.login_required
@_json_media_type
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
    # component(optional): only get votes for this component
    max_age = request.json.get('max_age', None)
    my_job_id = request.json.get('reporting_job_id', None)
    job_id = request.json.get('job_id', None)
    success = request.json.get('success', None)
    sequential_mode = request.json.get('sequential_mode', None)
    previous_job_id = request.json.get('previous_job_id', None)
    component = request.json.get('component', None)

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

    session = _get_db()
    try:
        if sequential_mode:
            # CI pipeline case
            vote = getVote(session, timestamp, success, previous_job_id,
                           component=component, fallback=False)
        else:
            # Normal case
            vote = getVote(session, timestamp, success, job_id,
                           component=component)
    except Exception as e:
        raise e

    newvote = CIVote(commit_id=vote.commit_id, ci_name=my_job_id,
                     ci_url='', ci_vote=False, ci_in_progress=True,
                     timestamp=int(time.time()), notes='',
                     user=auth.username(), component=vote.component)
    session.add(newvote)
    session.commit()

    commit = session.query(Commit).filter(
        Commit.status == 'SUCCESS',
        Commit.id == vote.commit_id).first()

    result = {'commit_hash': commit.commit_hash,
              'distro_hash': commit.distro_hash,
              'extended_hash': commit.extended_hash,
              'timestamp': newvote.timestamp,
              'job_id': newvote.ci_name,
              'success': newvote.ci_vote,
              'in_progress': newvote.ci_in_progress,
              'user': newvote.user,
              'component': newvote.component}
    return jsonify(result), 201


@app.route('/api/report_result', methods=['POST'])
@auth.login_required
@_json_media_type
def report_result():
    # job_id: name of CI
    # commit_hash: commit hash
    # distro_hash: distro hash
    # extended_hash(optional): extended hash
    # aggregate_hash: hash of aggregate.
    # url: URL where more information can be found
    # timestamp: CI execution timestamp
    # success: boolean
    # notes(optional): notes
    # Either commit_hash+distro_hash or aggregate_hash must be provided
    try:
        timestamp = request.json['timestamp']
        job_id = request.json['job_id']
        success = request.json['success']
        url = request.json['url']
    except KeyError:
        raise InvalidUsage('Missing parameters', status_code=400)

    commit_hash = request.json.get('commit_hash', None)
    distro_hash = request.json.get('distro_hash', None)
    extended_hash = request.json.get('extended_hash', None)
    aggregate_hash = request.json.get('aggregate_hash', None)

    if not commit_hash and not distro_hash and not aggregate_hash:
        raise InvalidUsage('Missing parameters', status_code=400)

    if commit_hash and not distro_hash:
        raise InvalidUsage('If commit_hash is provided, distro_hash '
                           'must be provided too', status_code=400)

    if distro_hash and not commit_hash:
        raise InvalidUsage('If distro_hash is provided, commit_hash '
                           'must be provided too', status_code=400)

    if (aggregate_hash and distro_hash) or (aggregate_hash and commit_hash):
        raise InvalidUsage('aggregate_hash and commit/distro_hash cannot be '
                           'combined', status_code=400)

    notes = request.json.get('notes', '')

    session = _get_db()
    # We have two paths here: one for votes on commit/distro/extended hash,
    # another for votes on aggregate_hash
    component = None
    if commit_hash:
        commit = _get_commit(session, commit_hash, distro_hash, extended_hash)
        if commit is None:
            raise InvalidUsage('commit_hash+distro_hash+extended_hash '
                               'combination not found', status_code=400)

        commit_id = commit.id
        out_ext_hash = commit.extended_hash
        component = commit.component
        vote = CIVote(commit_id=commit_id, ci_name=job_id, ci_url=url,
                      ci_vote=bool(strtobool(success)), ci_in_progress=False,
                      timestamp=int(timestamp), notes=notes,
                      user=auth.username(), component=component)
    else:
        out_ext_hash = None
        prom = session.query(Promotion).filter(
            Promotion.aggregate_hash == aggregate_hash).first()
        if prom is None:
            raise InvalidUsage('aggregate_hash not found',
                               status_code=400)

        vote = CIVote_Aggregate(ref_hash=aggregate_hash, ci_name=job_id,
                                ci_url=url, ci_vote=bool(strtobool(success)),
                                ci_in_progress=False, timestamp=int(timestamp),
                                notes=notes, user=auth.username())

    session.add(vote)
    session.commit()

    result = {'commit_hash': commit_hash,
              'distro_hash': distro_hash,
              'extended_hash': out_ext_hash,
              'aggregate_hash': aggregate_hash,
              'timestamp': timestamp,
              'job_id': job_id,
              'success': bool(strtobool(success)),
              'in_progress': False,
              'url': url,
              'notes': notes,
              'user': auth.username(),
              'component': component}
    return jsonify(result), 201


@app.route('/api/promote', methods=['POST'])
@auth.login_required
@_json_media_type
def promote():
    # commit_hash: commit hash
    # distro_hash: distro hash
    # extended_hash (optional): extended hash
    # promote_name: symlink name
    try:
        commit_hash = request.json['commit_hash']
        distro_hash = request.json['distro_hash']
        promote_name = request.json['promote_name']
    except KeyError:
        raise InvalidUsage('Missing parameters', status_code=400)

    extended_hash = request.json.get('extended_hash', None)

    # Check for invalid promote names
    if (promote_name == 'consistent' or promote_name == 'current'):
        raise InvalidUsage('Invalid promote_name %s' % promote_name,
                           status_code=403)

    config_options = _get_config_options(app.config['CONFIG_FILE'])

    session = _get_db()
    commit = _get_commit(session, commit_hash, distro_hash, extended_hash)
    if commit is None:
        raise InvalidUsage('commit_hash+distro_hash+extended_hash combination'
                           ' not found', status_code=400)

    # If the commit has been purged, do not move on
    if commit.flags & FLAG_PURGED:
        raise InvalidUsage('commit_hash+distro_hash+extended_hash has been '
                           'purged, cannot promote it', status_code=410)

    if config_options.use_components:
        base_directory = os.path.join(app.config['REPO_PATH'], "component/%s" %
                                      commit.component)
    else:
        base_directory = app.config['REPO_PATH']

    target_link = os.path.join(base_directory, promote_name)
    # Check for invalid target links, like ../promotename
    target_dir = os.path.dirname(os.path.abspath(target_link))
    if not os.path.samefile(target_dir, base_directory):
        raise InvalidUsage('Invalid promote_name %s' % promote_name,
                           status_code=403)

    # We should create a relative symlink
    yumrepodir = commit.getshardedcommitdir()
    if config_options.use_components:
        # In this case, the relative path should not include
        # the component part
        yumrepodir = yumrepodir.replace("component/%s/" % commit.component, '')

    # Remove symlink if it exists, so we can create it again
    if os.path.lexists(os.path.abspath(target_link)):
        os.remove(target_link)
    try:
        os.symlink(yumrepodir, target_link)
    except Exception as e:
        raise InvalidUsage("Symlink creation failed with error: %s" %
                           e, status_code=500)

    # Once the updated symlink is created, if we are using components
    # we need to update the top-level repo file
    repo_checksum = None
    if config_options.use_components:
        datadir = os.path.realpath(config_options.datadir)
        repo_checksum = aggregate_repo_files(promote_name, datadir, session,
                                             config_options.reponame,
                                             hashed_dir=True)

    timestamp = time.mktime(datetime.now().timetuple())
    promotion = Promotion(commit_id=commit.id, promotion_name=promote_name,
                          timestamp=timestamp, user=auth.username(),
                          component=commit.component,
                          aggregate_hash=repo_checksum)

    session.add(promotion)
    session.commit()

    repo_hash = _repo_hash(commit)
    repo_url = "%s/%s" % (config_options.baseurl, commit.getshardedcommitdir())

    result = {'commit_hash': commit_hash,
              'distro_hash': distro_hash,
              'extended_hash': commit.extended_hash,
              'repo_hash': repo_hash,
              'repo_url': repo_url,
              'promote_name': promote_name,
              'component': commit.component,
              'timestamp': timestamp,
              'user': auth.username(),
              'aggregate_hash': repo_checksum}
    return jsonify(result), 201


@app.route('/api/promote-batch', methods=['POST'])
@auth.login_required
@_json_media_type
def promote_batch():
    # hash_pairs: list of commit/distro hash pairs
    # promote_name: symlink name
    hash_list = []
    try:
        for pair in request.json:
            commit_hash = pair['commit_hash']
            distro_hash = pair['distro_hash']
            promote_name = pair['promote_name']
            extended_hash = pair.get('extended_hash', None)
            hash_item = [commit_hash, distro_hash, extended_hash, promote_name]
            hash_list.append(hash_item)
    except KeyError:
        raise InvalidUsage('Missing parameters', status_code=400)

    config_options = _get_config_options(app.config['CONFIG_FILE'])
    session = _get_db()
    # Now we will be running all checks for each combination
    # Check for invalid promote names
    for hash_item in hash_list:
        commit_hash = hash_item[0]
        distro_hash = hash_item[1]
        extended_hash = hash_item[2]
        promote_name = hash_item[3]
        if (promote_name == 'consistent' or promote_name == 'current'):
            raise InvalidUsage('Invalid promote_name %s for hash %s_%s' % (
                               promote_name, commit_hash, distro_hash),
                               status_code=403)
        commit = _get_commit(session, commit_hash, distro_hash, extended_hash)
        if commit is None:
            raise InvalidUsage('commit_hash+distro_hash+extended_hash '
                               'combination not found for %s_%s_%s' % (
                                commit_hash, distro_hash, extended_hash),
                               status_code=400)

        # If the commit has been purged, do not move on
        if commit.flags & FLAG_PURGED:
            raise InvalidUsage('commit_hash+distro_hash+extended_hash %s_%s_%s'
                               ' has been purged, cannot promote it' % (
                                commit_hash, distro_hash, extended_hash),
                               status_code=410)

        if config_options.use_components:
            base_directory = os.path.join(app.config['REPO_PATH'],
                                          "component/%s" % commit.component)
        else:
            base_directory = app.config['REPO_PATH']

        target_link = os.path.join(base_directory, promote_name)
        # Check for invalid target links, like ../promotename
        target_dir = os.path.dirname(os.path.abspath(target_link))
        if not os.path.samefile(target_dir, base_directory):
            raise InvalidUsage('Invalid promote_name %s' % promote_name,
                               status_code=403)

    # After all checks have been performed, do all promotions
    rollback_list = []
    for hash_item in hash_list:
        rollback_item = {}
        commit_hash = hash_item[0]
        distro_hash = hash_item[1]
        extended_hash = hash_item[2]
        promote_name = hash_item[3]
        commit = _get_commit(session, commit_hash, distro_hash, extended_hash)
        # We should create a relative symlink
        yumrepodir = commit.getshardedcommitdir()
        if config_options.use_components:
            base_directory = os.path.join(app.config['REPO_PATH'],
                                          "component/%s" %
                                          commit.component)
            # In this case, the relative path should not include
            # the component part
            yumrepodir = yumrepodir.replace("component/%s/" % commit.component,
                                            '')
        else:
            base_directory = app.config['REPO_PATH']

        target_link = os.path.join(base_directory, promote_name)
        rollback_item['target_link'] = target_link
        rollback_item['previous_link'] = None
        # Remove symlink if it exists, so we can create it again
        if os.path.lexists(os.path.abspath(target_link)):
            rollback_item['previous_link'] = os.readlink(
                os.path.abspath(target_link))
            os.remove(target_link)

        rollback_list.append(rollback_item)
        # This is the only destructive operation. If something fails here,
        # we will try to roll everything back
        try:
            os.symlink(yumrepodir, target_link)
        except Exception as e:
            _rollback_batch_promotion(rollback_list)
            raise InvalidUsage("Symlink creation failed with error: %s. "
                               "All previously created symlinks have been "
                               "rolled back." %
                               e, status_code=500)

        timestamp = time.mktime(datetime.now().timetuple())
        promotion = Promotion(commit_id=commit.id,
                              promotion_name=promote_name,
                              timestamp=timestamp, user=auth.username(),
                              component=commit.component,
                              aggregate_hash=None)
        session.add(promotion)

    # And finally, if we are using components, update the top-level
    # repo file
    repo_checksum = None
    if config_options.use_components:
        datadir = os.path.realpath(config_options.datadir)
        repo_checksum = aggregate_repo_files(promote_name, datadir, session,
                                             config_options.reponame,
                                             hashed_dir=True)
        promotion.aggregate_hash = repo_checksum
        session.add(promotion)

    # Close session and return the last promotion we did (which includes the
    # repo checksum)
    session.commit()
    repo_hash = _repo_hash(commit)
    repo_url = "%s/%s" % (config_options.baseurl, commit.getshardedcommitdir())
    result = {'commit_hash': commit_hash,
              'distro_hash': distro_hash,
              'extended_hash': commit.extended_hash,
              'repo_hash': repo_hash,
              'repo_url': repo_url,
              'promote_name': promote_name,
              'component': commit.component,
              'timestamp': timestamp,
              'user': auth.username(),
              'aggregate_hash': repo_checksum}
    return jsonify(result), 201


@app.route('/api/remote/import', methods=['POST'])
@auth.login_required
@_json_media_type
def remote_import():
    # repo_url: repository URL to import from
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
    session = _get_db()
    offset = request.args.get('offset', 0)

    votes = session.query(CIVote)
    votes = votes.filter(CIVote.ci_name != 'consistent')
    votes = votes.order_by(desc(CIVote.timestamp))
    votes = votes.offset(offset).limit(pagination_limit)
    count = votes.count()
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
        repodetail.success = votes.from_self().filter(
            CIVote.commit_id == commit_id, CIVote.ci_vote == 1).count()
        repodetail.failure = votes.from_self().filter(
            CIVote.commit_id == commit_id, CIVote.ci_vote == 0).count()
        repodetail.timestamp = votes.from_self().filter(
            CIVote.commit_id == commit_id).order_by(desc(CIVote.timestamp)).\
            first().timestamp
        repodetail.component = commit.component
        repolist.append(repodetail)

    repolist = sorted(repolist, key=lambda repo: repo.timestamp, reverse=True)

    config_options = _get_config_options(app.config['CONFIG_FILE'])

    return render_template('votes_general.j2',
                           target=config_options.target,
                           repodetail=repolist,
                           count=count,
                           limit=pagination_limit)


@app.route('/api/civotes_detail.html', methods=['GET'])
def get_civotes_detail():
    commit_hash = request.args.get('commit_hash', None)
    distro_hash = request.args.get('distro_hash', None)
    component = request.args.get('component', None)
    ci_name = request.args.get('ci_name', None)

    session = _get_db()

    commit_id = -1
    if commit_hash and distro_hash:
        commit = _get_commit(session, commit_hash, distro_hash)
        commit_id = commit.id if commit else -1
    elif not ci_name and not component:
        raise InvalidUsage("Please specify either commit_hash+distro_hash, "
                           "component or ci_name as parameters.",
                           status_code=400)

    config_options = _get_config_options(app.config['CONFIG_FILE'])

    return render_template('votes.j2',
                           target=config_options.target,
                           commitid=commit_id)


@app.route('/api/civotes_agg.html', methods=['GET'])
def get_civotes_agg():
    session = _get_db()
    offset = request.args.get('offset', 0)

    votes = session.query(CIVote_Aggregate)
    votes = votes.order_by(desc(CIVote_Aggregate.timestamp))
    votes = votes.offset(offset).limit(pagination_limit)
    count = votes.count()
    # Let's find all individual aggregate_hashes
    agg_id_list = []
    for vote in votes:
        if vote.ref_hash not in agg_id_list:
            agg_id_list.append(vote.ref_hash)

    # Populate list for aggregates
    agglist = []
    for ref_hash in agg_id_list:
        aggdetail = AggDetail()
        aggdetail.ref_hash = ref_hash
        aggdetail.success = votes.from_self().filter(
            CIVote_Aggregate.ref_hash == ref_hash,
            CIVote_Aggregate.ci_vote == 1).count()
        aggdetail.failure = votes.from_self().filter(
            CIVote_Aggregate.ref_hash == ref_hash,
            CIVote_Aggregate.ci_vote == 0).count()
        aggdetail.timestamp = votes.from_self().filter(
            CIVote_Aggregate.ref_hash == ref_hash).\
            order_by(desc(CIVote_Aggregate.timestamp)).\
            first().timestamp
        agglist.append(aggdetail)

    agglist = sorted(agglist, key=lambda repo: repo.timestamp, reverse=True)

    config_options = _get_config_options(app.config['CONFIG_FILE'])

    return render_template('votes_general_agg.j2',
                           target=config_options.target,
                           aggdetail=agglist,
                           count=count,
                           limit=pagination_limit)


@app.route('/api/civotes_agg_detail.html', methods=['GET'])
def get_civotes_agg_detail():
    ref_hash = request.args.get('ref_hash', None)
    ci_name = request.args.get('ci_name', None)

    if not ref_hash and not ci_name:
        raise InvalidUsage("Please specify either ref_hash or "
                           "ci_name as parameters.", status_code=400)

    config_options = _get_config_options(app.config['CONFIG_FILE'])

    return render_template('votes_agg.j2',
                           target=config_options.target)


@app.route('/api/report.html', methods=['GET'])
def get_report():
    config_options = _get_config_options(app.config['CONFIG_FILE'])

    return render_template('report.j2',
                           reponame='Detailed build report',
                           target=config_options.target,
                           src=config_options.source,
                           project_name=config_options.project_name,
                           limit=pagination_limit,
                           baseurl=config_options.baseurl)


@app.teardown_appcontext
def teardown_db(exception=None):
    session = flask_g.pop('db', None)
    if session is not None:
        closeSession(session)
