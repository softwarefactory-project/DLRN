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

from flask import g

from dlrn.api import app
from dlrn.api.utils import InvalidUsage
from dlrn.db import CIVote as CIVoteModel
from dlrn.db import CIVote_Aggregate as CIVoteAggModel
from dlrn.db import closeSession
from dlrn.db import Commit as CommitModel
from dlrn.db import getSession

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

    class Query(graphene.ObjectType):
        node = relay.Node.Field()
        commits = graphene.List(Commit,
                                projectName=graphene.String(),
                                component=graphene.String(),
                                status=graphene.String(),
                                offset=graphene.Int(),
                                limit=graphene.Int())
        civote = graphene.List(CIVote,
                               commitId=graphene.Int(),
                               ciName=graphene.String(),
                               ciVote=graphene.Boolean(),
                               ciInProgress=graphene.Boolean(),
                               timestamp=graphene.Int(),
                               user=graphene.String(),
                               component=graphene.String())

        civoteAgg = graphene.List(CIVoteAgg,
                                  refHash=graphene.String(),
                                  ciName=graphene.String(),
                                  ciVote=graphene.String(),
                                  ciInProgress=graphene.Boolean(),
                                  timestamp=graphene.Int(),
                                  user=graphene.String())

        def resolve_commits(self, info, **args):
            project_name = args.get("projectName", None)
            component = args.get("component", None)
            status = args.get("status", None)
            offset = args.get("offset", 0)
            limit = args.get("limit", pagination_limit)

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

            # Enforce pagination limit and offset
            query = query.limit(limit).offset(offset)
            return query.all()

        def resolve_civote(self, info, **args):
            # common variables
            offset = args.get("offset", 0)
            limit = args.get("limit", pagination_limit)

            # civote query params
            commit_id = args.get("commitId", None)
            ci_name = args.get("ciName", None)
            ci_vote = args.get("ciVote", None)
            ci_in_progress = args.get("ciInProgress", None)
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
            if ci_vote:
                query = query.filter(CIVoteModel.ci_vote == ci_vote)
            if ci_in_progress:
                query = query.filter(CIVoteModel.ci_in_progress ==
                                     ci_in_progress)
            if timestamp:
                query = query.filter(CIVoteModel.timestamp == timestamp)
            if user:
                query = query.filter(CIVoteModel.user == user)
            if component:
                query = query.filter(CIVoteModel.component == component)

            query = query.limit(limit).offset(offset)
            return query.all()

        def resolve_civoteAgg(self, info, **args):
            # common variables
            offset = args.get("offset", 0)
            limit = args.get("limit", pagination_limit)

            # civote query params
            ref_hash = args.get("refHash", None)
            ci_name = args.get("ciName", None)
            ci_vote = args.get("ciVote", None)
            ci_in_progress = args.get("ciInProgress", None)
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
            if ci_vote:
                query = query.filter(CIVoteAggModel.ci_vote == ci_vote)
            if ci_in_progress:
                query = query.filter(
                    CIVoteAggModel.ci_in_progress == ci_in_progress)
            if timestamp:
                query = query.filter(CIVoteAggModel.timestamp == timestamp)
            if user:
                query = query.filter(CIVoteAggModel.user == user)

            query = query.limit(limit).offset(offset)
            return query.all()

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
