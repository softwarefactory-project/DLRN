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

# NOTE(jpena): the graphene project is about to release version 3.0, but not
# all dependant projects support it, like graphene-sqlalchemy
# (see https://github.com/graphql-python/graphene-sqlalchemy/issues/248).
# In addition to this, Fedora includes a beta release of graphene 3.0.
# So for now we are making the graphql API endpoint optional.
try:
    from flask_graphql import GraphQLView
    import graphene
    from graphene import relay
    from graphene_sqlalchemy import SQLAlchemyObjectType
except ImportError:
    graphene = None

from datetime import datetime
from flask import g
from six.moves import configparser
from sqlalchemy import desc

from dlrn.api import app
from dlrn.api.utils import InvalidUsage
from dlrn.config import ConfigOptions
from dlrn.db import CIVote as CIVoteModel
from dlrn.db import CIVote_Aggregate as CIVoteAggModel
from dlrn.db import closeSession
from dlrn.db import Commit as CommitModel
from dlrn.db import getCommits
from dlrn.db import getSession
from dlrn.utils import import_object

# These values are the same as in dlrn_api.py
pagination_limit = 100
max_limit = 100

# We use this helper function to get the DB session in the app context,
# so it can be used by GraphQLView.as_view.
# See https://flask.palletsprojects.com/en/1.1.x/appcontext/#storing-data


def _get_db():
    if 'db' not in g:
        g.db = getSession(app.config['DB_PATH'])
    return g.db


def _get_config_options(config_file):
    cp = configparser.RawConfigParser()
    cp.read(config_file)
    return ConfigOptions(cp)


def _as_bool(value):
    if value is not None:
        return True if bool(value) else False
    return None


if graphene:
    class Commit(SQLAlchemyObjectType):
        class Meta:
            model = CommitModel
            interfaces = (relay.Node, )

    class CIVote(SQLAlchemyObjectType):
        class Meta:
            model = CIVoteModel
            interfaces = (relay.Node, )

    class CIVoteAgg(SQLAlchemyObjectType):
        class Meta:
            model = CIVoteAggModel
            interfaces = (relay.Node, )

    class PackageStatus(graphene.ObjectType):
        id = graphene.NonNull(
            graphene.ID,
            description="Unique identifier for package status")
        project_name = graphene.NonNull(
            graphene.String,
            description="Name of the project")
        status = graphene.NonNull(
            graphene.String,
            description="Build status, can be one of SUCCESS, FAILED, RETRY "
                        "or NO_BUILD")
        last_success = graphene.DateTime(
            description="If status is FAILED, date and time of the "
                        "last successful build")
        first_failure_commit = graphene.String(
            description="If status is FAILED, source commit has of the "
                        "first failed build")

    class Query(graphene.ObjectType):
        node = relay.Node.Field()
        commits = graphene.List(Commit,
                                projectName=graphene.String(),
                                component=graphene.String(),
                                status=graphene.String(),
                                offset=graphene.Int(),
                                limit=graphene.Int(),
                                commitHash=graphene.String(),
                                distroHash=graphene.String(),
                                extendedHash=graphene.String())
        civote = graphene.List(CIVote,
                               commitId=graphene.Int(),
                               ciName=graphene.String(),
                               ciVote=graphene.Boolean(),
                               ciInProgress=graphene.Boolean(),
                               timestamp=graphene.Int(),
                               user=graphene.String(),
                               component=graphene.String(),
                               offset=graphene.Int(),
                               limit=graphene.Int())

        civoteAgg = graphene.List(CIVoteAgg,
                                  refHash=graphene.String(),
                                  ciName=graphene.String(),
                                  ciVote=graphene.Boolean(),
                                  ciInProgress=graphene.Boolean(),
                                  timestamp=graphene.Int(),
                                  user=graphene.String(),
                                  offset=graphene.Int(),
                                  limit=graphene.Int())

        packageStatus = graphene.List(PackageStatus,
                                      projectName=graphene.String(),
                                      status=graphene.String())

        def resolve_commits(self, info, **args):
            project_name = args.get("projectName", None)
            component = args.get("component", None)
            status = args.get("status", None)
            offset = args.get("offset", 0)
            limit = args.get("limit", pagination_limit)
            commit_hash = args.get("commitHash", None)
            distro_hash = args.get("distroHash", None)
            extended_hash = args.get("extendedHash", None)

            # Make sure we do not exceed the pagination limit
            if limit > max_limit:
                limit = max_limit

            query = Commit.get_query(info)  # SQLAlchemy query
            if project_name:
                query = query.filter(CommitModel.project_name == project_name)
            if component:
                query = query.filter(CommitModel.component == component)
            if status:
                query = query.filter(CommitModel.status == status)
            if commit_hash:
                query = query.filter(CommitModel.commit_hash == commit_hash)
            if distro_hash:
                query = query.filter(CommitModel.distro_hash == distro_hash)
            if extended_hash:
                query = query.filter(
                    CommitModel.extended_hash.like(extended_hash))

            # Enforce pagination limit and offset
            query = query.order_by(desc(CommitModel.id)).limit(limit).\
                offset(offset)
            return query.all()

        def resolve_civote(self, info, **args):
            # common variables
            offset = args.get("offset", 0)
            limit = args.get("limit", pagination_limit)

            # civote query params
            commit_id = args.get("commitId", None)
            ci_name = args.get("ciName", None)
            ci_vote = _as_bool(args.get("ciVote", None))
            ci_in_progress = _as_bool(args.get("ciInProgress", None))
            timestamp = args.get("timestamp", None)
            user = args.get("user", None)
            component = args.get("component", None)

            # Make sure we do not exceed the pagination limit
            if limit > max_limit:
                limit = max_limit
            query = CIVote.get_query(info)

            if commit_id:
                query = query.filter(CIVoteModel.commit_id == commit_id)
            if ci_name:
                query = query.filter(CIVoteModel.ci_name == ci_name)
            if ci_vote is not None:
                query = query.filter(CIVoteModel.ci_vote == ci_vote)
            if ci_in_progress is not None:
                query = query.filter(CIVoteModel.ci_in_progress ==
                                     ci_in_progress)
            if timestamp:
                query = query.filter(CIVoteModel.timestamp == timestamp)
            if user:
                query = query.filter(CIVoteModel.user == user)
            if component:
                query = query.filter(CIVoteModel.component == component)

            query = query.order_by(desc(CIVoteModel.id)).limit(limit).\
                offset(offset)
            return query.all()

        def resolve_civoteAgg(self, info, **args):
            # common variables
            offset = args.get("offset", 0)
            limit = args.get("limit", pagination_limit)

            # civote query params
            ref_hash = args.get("refHash", None)
            ci_name = args.get("ciName", None)
            ci_vote = _as_bool(args.get("ciVote", None))
            ci_in_progress = _as_bool(args.get("ciInProgress", None))
            timestamp = args.get("timestamp", None)
            user = args.get("user", None)

            # Make sure we do not exceed the pagination limit
            if limit > max_limit:
                limit = max_limit

            query = CIVoteAgg.get_query(info)

            if ref_hash:
                query = query.filter(CIVoteAggModel.ref_hash == ref_hash)
            if ci_name:
                query = query.filter(CIVoteAggModel.ci_name == ci_name)
            if ci_vote is not None:
                query = query.filter(CIVoteAggModel.ci_vote == ci_vote)
            if ci_in_progress is not None:
                query = query.filter(
                    CIVoteAggModel.ci_in_progress == ci_in_progress)
            if timestamp:
                query = query.filter(CIVoteAggModel.timestamp == timestamp)
            if user:
                query = query.filter(CIVoteAggModel.user == user)

            query = query.order_by(desc(CIVoteAggModel.id)).limit(limit).\
                offset(offset)
            return query.all()

        def resolve_packageStatus(self, info, **args):
            project_name = args.get("projectName", None)
            status = args.get("status", None)

            if project_name:
                packages = [{'name': project_name}]
            else:
                # The only canonical source of information for the package list
                # is rdoinfo (or whatever pkginfo driver we use)
                config_options = _get_config_options(app.config['CONFIG_FILE'])
                pkginfo_driver = config_options.pkginfo_driver
                pkginfo = import_object(pkginfo_driver,
                                        cfg_options=config_options)
                packages = pkginfo.getpackages(tags=config_options.tags)

            i = 0
            result = []
            session = _get_db()
            for package in packages:
                pkg = package['name']
                commits = getCommits(session, project=pkg, limit=1)
                # No builds
                if commits.count() == 0:
                    if not status or status == 'NO_BUILD':
                        result.append({'id': i,
                                       'project_name': pkg,
                                       'status': 'NO_BUILD'})
                    i += 1
                    continue
                last_build = commits.first()
                # last build was successul
                if last_build.status == "SUCCESS":
                    if not status or status == 'SUCCESS':
                        result.append({'id': i,
                                       'project_name': pkg,
                                       'status': 'SUCCESS'})
                else:
                    if not status or status == last_build.status:
                        # Retrieve last successful build
                        commits = getCommits(session, project=pkg,
                                             with_status="SUCCESS", limit=1)
                        # No successful builds
                        if commits.count() == 0:
                            last_success = datetime(1970, 1, 1, 0, 0, 0)
                        else:
                            last_success = datetime.fromtimestamp(
                                commits.first().dt_build)
                        result.append({'id': i,
                                       'project_name': pkg,
                                       'status': 'FAILED',
                                       'last_success': last_success,
                                       'first_failure_commit':
                                       last_build.commit_hash})
                i += 1
            return result

    schema = graphene.Schema(query=Query, types=[])
    # NOTE(jpena): set graphiql=True to enable the GraphiQL page, which is
    #              very useful for testing
    app.add_url_rule('/api/graphql', view_func=GraphQLView.as_view(
        'graphql',
        schema=schema,
        graphiql=False,
        get_context=lambda: {'session': _get_db()}
    ))

    @app.teardown_appcontext
    def teardown_db(exception=None):
        session = g.pop('db', None)
        if session is not None:
            closeSession(session)

else:
    @app.route('/api/graphql', methods=['GET', 'POST'])
    def graphql_missing_libraries():
        raise InvalidUsage('Missing libraries, /api/graphql endpoint is not'
                           'available', status_code=501)
