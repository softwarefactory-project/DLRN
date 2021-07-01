###################
GraphQL information
###################

**************
GraphQL schema
**************

This page describes the schema definition used for the GraphQL types and queries
available through the DLRN API.

You can generate a human-readable version of the schema by running the following
script:

.. code-block:: python

    from dlrn.api.graphql import schema
    from graphql.utils import schema_printer

    schema_str = schema_printer.print_schema(schema)
    print(schema_str)

Types
-----

.. code-block::

    type Commit {
        id: ID!
        type: String
        dtCommit: Int
        dtDistro: Int
        dtExtended: Int
        dtBuild: Int
        projectName: String
        repoDir: String
        distgitDir: String
        commitHash: String
        distroHash: String
        extendedHash: String
        commitBranch: String
        status: String
        component: String
        artifacts: String
        notes: String
        flags: Int
        civotes(before: String, after: String, first: Int, last: Int): CIVoteConnection
    }

The Commit type is converted from its schema in the database.

.. code-block::

   type CIVote {
        id: ID!
        commitId: Int!
        ciName: String
        ciUrl: String
        ciVote: Boolean
        ciInProgress: Boolean
        timestamp: Int
        notes: String
        user: String
        component: String
        commit: Commit
   }

Like Commit type, CIVote is converted from its schema to database.

.. code-block::

    type CIVoteAgg {
        id: ID!
        refHash: String!
        ciName: String
        ciUrl: String
        ciVote: Boolean
        ciInProgress: Boolean
        timestamp: Int
        notes: String
        user: String
    }

The CIVoteAgg is converted from CIVote_Aggregate DB schema.

.. code-block::

    type PackageStatus {
        id: ID!
        projectName: String!
        status: String!
        lastSuccess: DateTime
        firstFailureCommit: String
    }

The PackageStatus type is generated directly in Graphene.

Queries
-------

All queries should conform to the GraphQL language. When more than one item is
returned, they will be sorted by descending id order, which means newer commits
or CI Votes are displayed first.

Note that you will need to specify which fields from the return type you want
to get. See `the GraphQL tutorial <https://graphql.org/learn/queries/>`_
for additional details.

Available queries:

* commits

.. code-block::

    commits(
        projectName: String
        component: String
        status: String
        offset: Int
        limit: Int
        commitHash: String
        distroHash: String
        extendedHash: String
    ): [Commit]

Arguments:

- projectName: limit the results to the commits belonging to the specified project name.
- component: limit the results to the commits belonging to the specified component.
- status: limit the results to the commits with the specified status.
- offset: return the results after the specified entry.
- limit: return a maximum amount of commits (100 by default, cannot be higher than 100).
- commitHash: limit the results to the commits containing the specified commit hash.
- distroHash: limit the results to the commits containing the specified distro hash.
- extendedHash: limit the results to the commits containing the specified extended hash.
  In this case, extendedHash can contain wildcards in SQL format, so setting extendedHash
  to "foo%" in the query will return all commits with an extended hash that starts by "foo".


* civote

.. code-block::

   civote(
        commitId: Int
        ciName: String
        ciVote: Boolean
        ciInProgress: Boolean
        timestamp: Int
        user: String
        component: String
        offset: Int
        limit: Int
    ): [CIVote]

Arguments:
- commitId: limit the results to the civote belonging to the commit id.
- ciName: limit the results to the civote belonging to the CI name.
- ciVote: limit the results to the civote belonging to the voting CI.
- ciInProgress: limit the results to the civote belonging to "In Progress" state.
- timestamp: limit the results to the civote belonging to the specified timestamp.
- user: limit the results to the civote belonging to the specified user.
- component: limit the results to the civote belonging to the specified component.
- offset: return the results after the specified entry.
- limit: return a maximum amount of commits (100 by default, cannot be higher than 100).


* civoteAgg

.. code-block::

    civoteAgg (
        refHash: String
        ciName: String
        ciVote: Boolean
        ciInProgress: Boolean
        timestamp: Int
        user: String
        offset: Int
        limit: Int
    ): [CIVote_Aggregate]

Arguments:
- refHash: limit the results to the civote_aggregation belonging to the specified reference hash.
- ciName: limit the results to the civote_aggregation belonging to the specified CI name.
- ciVote: limit the results to the civote_aggregation belonging to the specified CI vote.
- ciInProgress: limit the results to the civote_aggregation belonging to the specified CI in progress state.
- timestamp: limit the results to the civote_aggregation belonging to the specified timestamp.
- user: limit the results to the civote_aggregation belonging to the specified user.
- offset: return the results after the specified entry.
- limit: return a maximum amount of commits (100 by default, cannot be higher than 100).


* packageStatus

.. code-block::

    packageStatus(
        projectName: String,
        status: String
    ): [PackageStatus]

Arguments:
- projectName: limit the results to the status of the specified project name.
- status: limit the results to the packages with the specified status.

*****************************
Querying the GraphQL endpoint
*****************************

As described in the `GraphQL website <https://graphql.org/learn/serving-over-http/#http-methods-headers-and-body>`_,
when GraphQL is served over HTTP it is possible to run queries using both GET and POST
methods.

GET example
-----------

.. code-block:: bash

    $ curl 'http://localhost:5000/api/graphql?query=\{commits\{component%20projectName\}\}'

Note that in the curl command line we are escaping braces and replacing blank spaces
with %20. The equivalent query when run from a broswer would be
``http://localhost:5000/api/graphql?query={ commits { component projectName } }``.

POST example
------------

.. code-block:: bash

    $ curl http://localhost:5000/api/graphql -H POST -d 'query={ commits { component projectName } }'

In this case, we are using a POST method, and the query is JSON-encoded. Note that it is
also possible to use a GET method with a JSON-encoded payload.
