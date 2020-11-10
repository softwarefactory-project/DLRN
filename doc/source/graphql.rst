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
    }

The Commit type is converted from its schema in the database.

.. code-block::

   type civote {
        commitId: Int
        ciName: String
        ciVote: String
        ciInProgress: Bool
        timestamp: Int
        user: String
        component: String
   }

Like Commit type, CIVote is converted from its schema to database.

Queries
-------

All queries should conform to the GraphQL language. Note that you will need to specify
which fields from the return type you want to get. See `the GraphQL tutorial <https://graphql.org/learn/queries/>`_
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
    ): [Commit]

Arguments:

- projectName: limit the results to the commits beloging to the specified project name.
- component: limit the results to the commits beloging to the specified component.
- status: limit the results to the commits with the specified status.
- offset: return the results after the specified entry.
- limit: return a maximum amount of commits (100 by default, cannot be higher than 100).


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
    ): [CIVote]

Arguments:

- commitId: limit the results to the civote beloging to the commit id.
- ciName: limit the results to the civote beloging to the CI name.
- ciVote: limit the results to the civote beloging to the voting CI.
- ciInProgress: limit the results to the civote beloging to "In Progress" state.
- timestamp: limit the results to the civote beloging to the specified timestamp.
- user: limit the results to the civote beloging to the specified user.
- component: limit the results to the civote beloging to the specified component.


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
