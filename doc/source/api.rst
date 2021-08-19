##############
API definition
##############

*******************
General information
*******************

``GET`` operations will be non-authenticated. ``POST`` operations will require
authentication using username+password.

Password information is stored in the database using the SHA512 hash.

For POST operations, all data will be sent/received using JSON objects, unless
stated otherwise. For GET operations, the recommended method is to send data
using in-query parameters. JSON in-body objects still work, but are deprecated
and expected to be removed in a future version.

*********
API calls
*********

GET /api/health
---------------

Check the API server health. This will trigger a database connection to
ensure all components are in working condition.

Normal response codes: 200

Error response codes: 401

Response:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
result               string      A simple success string
===================  ==========  ==============================================================

POST /api/health
----------------

Check the API server health. This will trigger a database connection to
ensure all components are in working condition. In addition to this, the
POST call will check authentication.

Normal response codes: 200

Error response codes: 401

Response:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
result               string      A simple success string
===================  ==========  ==============================================================

GET /api/last_tested_repo
-------------------------

Get the last tested repo since a specific time.

If a ``job_id`` is specified, the order of precedence for the repo returned is:

- The last tested repo within that timeframe for that CI job.
- The last tested repo within that timeframe for any CI job, so we can have
  several CIs converge on a single repo.
- The last "consistent" repo, if no repo has been tested in the timeframe.

If ``sequential_mode`` is set to true, a different algorithm is used. Another
parameter ``previous_job_id`` needs to be specified, and the order of
precedence for the repo returned is:

- The last tested repo within that timeframe for the CI job described by
  ``previous_job_id``.
- If no repo for ``previous_job_id`` is found, an error will be returned

The sequential mode is meant to be used by CI pipelines, where a CI (n) job needs
to use the same repo tested by CI (n-1).

Normal response codes: 200

Error response codes: 400


Request:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
max_age              integer     Maximum age (in hours) for the repo to be considered. Any repo
                                 tested or being tested after "now - max_age" will be taken
                                 into account. If set to 0, all repos will be considered.
success              boolean     If set to a value, find repos with a successful/unsuccessful
                     (optional)  vote (as specified). If not set, any tested repo will be
                                 considered.
job_id               string      Name of the CI that sent the vote. If not set, no filter will
                     (optional)  be set on CI.
sequential_mode      boolean     Use the sequential mode algorithm. In this case, return the
                     (optional)  last tested repo within that timeframe for the CI job
                                 described by previous_job_id. Defaults to false.
previous_job_id      string      If sequential_mode is set to true, look for jobs tested by
                     (optional)  the CI identified by previous_job_id.
component            string      Only report votes associated to this component
                     (optional)
===================  ==========  ==============================================================

Response:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
commit_hash          string      commit_hash of tested repo
distro_hash          string      distro_hash of tested repo
extended_hash        string      extended_hash of tested repo
success              boolean     whether the test was successful or not
job_id               string      name of the CI sending the vote
in_progress          boolean     is this CI job still in-progress?
timestamp            integer     timestamp for the repo
user                 string      user who created the CI vote
component            string      Component associated to the commit/distro hash
===================  ==========  ==============================================================


GET /api/repo_status
--------------------

Get all the CI reports for a specific repository.

Normal response codes: 200

Error response codes: 400


Request:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
commit_hash          string      commit_hash of the repo to fetch information for
distro_hash          string      distro_hash of the repo to fetch information for
extended_hash        string      If set, extended_hash of the repo to fetch information for.
                     (optional)  If not set, the latest commit with the commit/distro hash
                                 combination will be reported.
success              boolean     If set to a value, only return the CI reports with the
                     (optional)  specified vote. If not set, return all CI reports.
===================  ==========  ==============================================================

Response:

The JSON output will contain an array where each item contains:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
job_id               string      name of the CI sending the vote
commit_hash          string      commit_hash of tested repo
distro_hash          string      distro_hash of tested repo
extended_hash        string      extended_hash of tested repo
url                  string      URL where to find additional information from the CI execution
timestamp            integer     Timestamp (in seconds since the epoch)
in_progress          boolean     False -> is this CI job still in-progress?
success              boolean     Was the CI execution successful?
notes                Text        Additional notes
user                 string      user who created the CI vote
component            string      Component associated to the commit/distro hash
===================  ==========  ==============================================================

GET /api/agg_status
--------------------

Get all the CI reports for a specific aggregated repository.

Normal response codes: 200

Error response codes: 400


Request:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
aggregate_hash       string      hash of the aggregated repo to fetch information for
success              boolean     If set to a value, only return the CI reports with the
                     (optional)  specified vote. If not set, return all CI reports.
===================  ==========  ==============================================================

Response:

The JSON output will contain an array where each item contains:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
job_id               string      name of the CI sending the vote
aggregate_hash       string      hash of tested aggregated repo
url                  string      URL where to find additional information from the CI execution
timestamp            integer     Timestamp (in seconds since the epoch)
in_progress          boolean     False -> is this CI job still in-progress?
success              boolean     Was the CI execution successful?
notes                Text        Additional notes
user                 string      user who created the CI vote
===================  ==========  ==============================================================

GET /api/promotions
-------------------

Get all the promotions, optionally for a specific repository or promotion name.  The output
will be sorted by the promotion timestamp, with the newest first, and limited to 100 results
per query.

Normal response codes: 200

Error response codes: 400

Request:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
commit_hash          string      If set, commit_hash of the repo to use as filter key.
                     (optional)  Requires distro_hash.
distro_hash          string      If set, commit_hash of the repo to use as filter key.
                     (optional)  Requires commit_hash.
extended_hash        string      If set, extended_hash of the repo to use as filter key. 
                     (optional)  Requires commit_hash and distro_hash.
aggregate_hash       string      If set, use the generated aggregate_hash as filter key.
                     (optional)  Only makes sense when components are enabled.
promote_name         string      If set to a value, filter results by the specified promotion
                     (optional)  name.
offset               integer     If set to a value, skip the initial <offset> promotions.
                     (optional)
limit                integer     If set to a value, limit the returned promotions amount
                     (optional)  to <limit>.
component            string      If set to a value, only report promotions for this component.
                     (optional)
===================  ==========  ==============================================================

The JSON output will contain an array where each item contains:

===============  ==========  ==============================================================
Parameter          Type                             Description
===============  ==========  ==============================================================
commit_hash      string      commit_hash of the promoted repo
distro_hash      string      distro_hash of the promoted repo
extended_hash    string      extended_hash of the promoted repo
agggregate_hash  string      Hash of the aggregated repo file, when using components
repo_hash        string      Repository hash, composed of the commit_hash and short
                             distro_hash
repo_url         string      Full URL of the promoted repository
promote_name     string      name used for the promotion
component        string      Component associated to the commit/distro hash
timestamp        integer     Timestamp (in seconds since the epoch)
user             string      user who created the promotion
===============  ==========  ==============================================================

The array will be sorted by the promotion timestamp, with the newest first.

GET /api/metrics/builds
-----------------------

Retrieve statistics on the number of builds during a certain period, optionally filtered by
package name.

Normal response codes: 200

Error response codes: 400

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
start_date           string      Start date for the period, in YYYY-mm-dd format. The start
                                 date is included in the reference period.
end_date             string      End date for the period, in YYYY-mm-dd format. The end date is
                                 not included in the period, so it is
                                 start_date <= date < end_date.
package_name         string      If set to a value, report metrics only for the specified
                     (optional)  package name.
===================  ==========  ==============================================================


Response:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
succeeded            integer     Number of commits that were built successfully in the period
failed               integer     Number of commits that failed to build in the period
total                integer     Total number of commits processed in the period
===================  ==========  ==============================================================

GET /metrics
------------

Retrieve statistics on the absolute number of builds for the builder, in Prometheus format.

Normal response codes: 200

Error response codes: 400

No parameters.

Response:

In text/plain format:
::

    # HELP dlrn_builds_succeeded_total Total number of successful builds
    # TYPE dlrn_builds_succeeded_total counter
    dlrn_builds_succeeded_total{baseurl="http://trunk.rdoproject.org/centos8/"} 9296.0
    # HELP dlrn_builds_failed_total Total number of failed builds
    # TYPE dlrn_builds_failed_total counter
    dlrn_builds_failed_total{baseurl="http://trunk.rdoproject.org/centos8/"} 244.0
    # HELP dlrn_builds_retry_total Total number of builds in retry state
    # TYPE dlrn_builds_retry_total counter
    dlrn_builds_retry_total{baseurl="http://trunk.rdoproject.org/centos8/"} 119.0
    # HELP dlrn_builds_total Total number of builds
    # TYPE dlrn_builds_total counter
    dlrn_builds_total{baseurl="http://trunk.rdoproject.org/centos8/"} 9659.0

GET /api/graphql
----------------

Query the `GraphQL interface <https://graphql.org/>`_. The available GraphQL schema is described
in detail in `its own <graphql.html>`_ documentation.


POST /api/last_tested_repo
--------------------------

Get the last tested repo since a specific time (optionally for a CI job),
and add an "in progress" entry in the CI job table for this.

If a job_id is specified, the order of precedence for the repo returned is:

- The last tested repo within that timeframe for that CI job.
- The last tested repo within that timeframe for any CI job, so we can have
  several CIs converge on a single repo.
- The last "consistent" repo, if no repo has been tested in the timeframe.

If ``sequential_mode`` is set to true, a different algorithm is used. Another
parameter ``previous_job_id`` needs to be specified, and the order of
precedence for the repo returned is:

- The last tested repo within that timeframe for the CI job described by
  ``previous_job_id``.
- If no repo for ``previous_job_id`` is found, an error will be returned

The sequential mode is meant to be used by CI pipelines, where a CI (n) job needs
to use the same repo tested by CI (n-1).

Normal response codes: 201

Error response codes: 400, 415


Request:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
max_age              integer     Maximum age (in hours) for the repo to be considered. Any repo
                                 tested or being tested after "now - max_age" will be taken
                                 into account. If set to 0, all repos will be considered.
reporting_job_id     string      Name of the CI that will add the "in progress" entry in the CI
                                 job table
success              boolean     If set to a value, find repos with a successful/unsuccessful
                     (optional)  vote (as specified). If not set, any tested repo will be
                                 considered.
job_id               string      name of the CI that sent the vote. If not set, no filter will
                     (optional)  be set on CI.
sequential_mode      boolean     Use the sequential mode algorithm. In this case, return the
                     (optional)  last tested repo within that timeframe for the CI job
                                 described by previous_job_id. Defaults to false.
previous_job_id      string      If sequential_mode is set to true, look for jobs tested by
                     (optional)  the CI identified by previous_job_id.
component            string      Only report votes associated to this component
                     (optional)
===================  ==========  ==============================================================

Response:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
commit_hash          string      commit_hash of tested repo
distro_hash          string      distro_hash of tested repo
extended_hash        string      extended_hash of tested repo
success              boolean     whether the test was successful or not
job_id               string      name of the CI sending the vote
in_progress          boolean     True -> is this CI job still in-progress?
timestamp            integer     Timestamp for this CI Vote (taken from the DLRN system time)
user                 string      user who created the CI vote
component            string      Component associated to the commit/distro hash
===================  ==========  ==============================================================


POST /api/report_result
-----------------------

Report the result of a CI job.

It is possible to report results on two sets of objets:

- A commit, represented by a ``commit_hash`` and a ``distro_hash``.
- An aggregated repo, represented by an ``aggregate_hash``.

One of those two parameters needs to be specified, otherwise the call will
return an error.

Normal response codes: 201

Error response codes: 400, 415, 500

Request:

==============  ==========  ==============================================================
  Parameter       Type                             Description
==============  ==========  ==============================================================
job_id          string      name of the CI sending the vote
commit_hash     string      commit_hash of tested repo
distro_hash     string      distro_hash of tested repo
extended_hash   string      extended_hash of the tested repo. If not set, the latest
                (optional)  commit with the commit_hash/distro_hash combination will be
                            used
aggregate_hash  string      hash of the aggregated repo that was tested
url             string      URL where to find additional information from the CI execution
timestamp       integer     Timestamp (in seconds since the epoch)
success         boolean     Was the CI execution successful?
notes           Text        Additional notes (optional)
==============  ==========  ==============================================================

Response:

==============  ==========  ==============================================================
Parameter         Type                             Description
==============  ==========  ==============================================================
job_id          string      name of the CI sending the vote
commit_hash     string      commit_hash of tested repo
distro_hash     string      distro_hash of tested repo
extended_hash   string      extended_hash of tested repo
url             string      URL where to find additional information from the CI execution
timestamp       integer     Timestamp (in seconds since the epoch)
in_progress     boolean     False -> is this CI job still in-progress?
success         boolean     Was the CI execution successful?
notes           Text        Additional notes
user            string      user who created the CI vote
component       string      Component associated to the commit/distro hash
==============  ==========  ==============================================================

POST /api/promote
-----------------

Promote a repository. This can be implemented as a local symlink creation in the DLRN
worker, or any other form in the future.

Note the API will refuse to promote using promote_name="consistent" or "current", since
those are reserved keywords for DLRN. Also, a commit that has been purged from the
database cannot be promoted.

When the projects.ini ``use_components`` option is set to ``true``, an aggregated repo
file will be created, including the repo files of all components that were promoted with
the same promotion name. The hash of that file will be returned as ``aggregated_hash``.
If the option is set to ``false``, a null value will be returned.

Normal response codes: 201

Error response codes: 400, 403, 410, 415, 500

Request:

==============  ==========  ==============================================================
  Parameter       Type                             Description
==============  ==========  ==============================================================
commit_hash     string      commit_hash of the repo to be promoted
distro_hash     string      distro_hash of the repo to be promoted
extended_hash   string      extended_hash of the repo to be promoted (optional). If not
                            specified, the API will take the last commit built with the
                            commit and distro hash.
promote_name    string      name to be used for the promotion. In the current
                            implementation, this is the name of the symlink to be created
==============  ==========  ==============================================================

Response:

===============  ==========  ==============================================================
Parameter         Type                             Description
===============  ==========  ==============================================================
commit_hash      string      commit_hash of the promoted repo
distro_hash      string      distro_hash of the promoted repo
extended_hash    string      extended_hash of the promoted repo
repo_hash        string      Repository hash, composed of the commit_hash and short
                             distro_hash
repo_url         string      Full URL of the promoted repository
promote_name     string      name used for the promotion
component        string      Component associated to the commit/distro hash
timestamp        integer     Timestamp (in seconds since the epoch)
user             string      user who created the promotion
agggregate_hash  string      Hash of the aggregated repo file, when using components
===============  ==========  ==============================================================

POST /api/promote-batch
-----------------------
Promote a list of commits. This is the equivalent of calling /api/promote multiple times,
one with each commit/distro_hash combination. The only difference is that the call is
atomic, and when components are enabled, the aggregated repo files are only updated once.

If any of the individual promotions fail, the API call will try its best to undo all the
changes to the file system (e.g. symlinks).

Note the API will refuse to promote using promote_name="consistent" or "current", since
those are reserved keywords for DLRN. Also, a commit that has been purged from the
database cannot be promoted.

Normal response codes: 201

Error response codes: 400, 403, 410, 415, 500

Request:

The JSON input will contain an array where each item contains:

==============  ==========  ==============================================================
  Parameter       Type                             Description
==============  ==========  ==============================================================
commit_hash     string      commit_hash of the repo to be promoted
distro_hash     string      distro_hash of the repo to be promoted
extended_hash   string      extended_hash of the repo to be promoted (optional). If not
                            specified, the API will take the last commit built with the
                            commit and distro hash.
promote_name    string      name to be used for the promotion. In the current
                            implementation, this is the name of the symlink to be created
==============  ==========  ==============================================================

Response:

===============  ==========  ==============================================================
Parameter          Type                             Description
===============  ==========  ==============================================================
commit_hash      string      commit_hash of the promoted repo
distro_hash      string      distro_hash of the promoted repo
extended_hash    string      extended_hash of the promoted repo
repo_hash        string      Repository hash, composed of the commit_hash and short
                             distro_hash
repo_url         string      Full URL of the promoted repository
promote_name     string      name used for the promotion
component        string      Component associated to the commit/distro hash
timestamp        integer     Timestamp (in seconds since the epoch)
user             string      user who created the promotion
agggregate_hash  string      Hash of the aggregated repo file, when using components
===============  ==========  ==============================================================

This is the last promoted commit.

POST /api/remote/import
-----------------------

Import a commit built by another instance. This API call mimics the behavior of the
``dlrn-remote`` command, with the only exception of not being able to specify a custom
rdoinfo location.

Normal response codes: 201

Error response codes: 400, 415, 500

Request:

==============  ==========  ==============================================================
  Parameter       Type                             Description
==============  ==========  ==============================================================
repo_url        string      Base repository URL for remotely generated repo
==============  ==========  ==============================================================

Response:

==============  ==========  ==============================================================
Parameter         Type                             Description
==============  ==========  ==============================================================
repo_url        string      Base repository URL for imported remote repo
==============  ==========  ==============================================================

*********************************
Running the API server using WSGI
*********************************

Requirements
------------

It is possible to run the DLRN API server as a WSGI process in Apache. To do
this, you need to install the following packages:


.. code-block:: bash

    $ sudo yum -y install httpd mod_wsgi

WSGI file and httpd configuration
---------------------------------

To run the application, you need to create a WSGI file. For example, create
``/var/www/dlrn/dlrn-api.wsgi`` with the following contents:

.. code-block:: python

    import os
    import sys
    sys.path.append('/home/centos-master/.venv/lib/python2.7/site-packages/')

    def application(environ, start_response):
        os.environ['CONFIG_FILE'] = environ['CONFIG_FILE']
        from dlrn.api import app
        return app(environ, start_response)

You need to change the path appended using ``sys.path.append`` to be the path
to the virtualenv where you have installed DLRN.

Then, create an httpd configuration file to load the WSGI application. The
following is an example file, named ``/etc/httpd/conf.d/wsgi-dlrn.conf``:

.. code-block:: none

    <VirtualHost *>
        ServerName example.com

        WSGIDaemonProcess dlrn  user=centos-master group=centos-master threads=5
        WSGIScriptAlias / /var/www/dlrn/dlrn-api-centos-master.wsgi
        SetEnv CONFIG_FILE /etc/dlrn/dlrn-api.cfg

        <Directory /var/www/dlrn>
            WSGIProcessGroup dlrn
            WSGIApplicationGroup %{GLOBAL}
            WSGIScriptReloading On
            WSGIPassAuthorization On
            Order deny,allow
            Allow from all
        </Directory>
    </VirtualHost>

Set ``CONFIG_FILE`` to the path of the DLRN configuration file, and make sure
you specify the right user and group for the ``WSGIDaemonProcess`` line.

Set ``DLRN_DEBUG`` to enable debug logs and set ``DLRN_LOG_FILE`` to the path
of a logfile.


DLRN API configuration
----------------------

The DLRN API take a default configuration from file ``dlrn/api/config.py``.
Since it may not match your actual configuration when deployed as an WSGI
application, you can create a configuration file, ``/etc/dlrn/dlrn-api.cfg``
in the above example, with the following syntax:

.. code-block:: ini

    DB_PATH = 'sqlite:////home/centos-master/DLRN/commits.sqlite'
    REPO_PATH = '/home/centos-master/DLRN/data/repos'
    CONFIG_FILE = 'projects.ini'

Where ``DB_PATH`` is the path to the SQLite database for your environment,
``REPO_PATH`` will point to the base directory for the generated repositories,
and ``CONFIG_FILE`` will point to the projects.ini file used when running
DLRN.

***************
User management
***************

There is a command-line tool to manage DLRN API users:

.. code-block:: console

    usage: dlrn-user [-h] [--config-file CONFIG_FILE] {create,delete,update} ...

    arguments:
      -h, --help            show this help message and exit
      --config-file CONFIG_FILE
                            Config file. Default: projects.ini

    subcommands:
      available subcommands

      {create,delete,update}
        create              Create a user
        delete              Delete a user
        update              Update a user

User creation
-------------

Use the ``create`` subcommand to create a new user.

.. code-block:: shell-session

    $ dlrn-user create --username foo --password bar

If you do not specify a password in the command-line, you will be prompted to
enter one interactively.

User update
-----------

You can use the ``update`` subcommand to change user data. Currently, only the
password can be changed.

.. code-block:: shell-session

    $ dlrn-user update --username foo --password new

User deletion
-------------

Use the  ``delete`` subcommand to delete a user.

.. code-block:: shell-session

    $ dlrn-user delete --username foo

The command will ask for confirmation, and you have to type "YES" (without the
quotes) in uppercase to delete the user. You can also avoid the confirmation
request by adding the ``--force`` parameter.

.. code-block:: shell-session

    $ dlrn-user delete --username foo --force
