######################
API definition (draft)
######################

*******************
General information
*******************

``GET`` operations will be non-authenticated. ``POST`` operations will require
authentication using username+password.

Password information is stored in the database using the SHA512 hash.

All data will be sent/received using JSON objects, unless stated otherwise.

*********
API calls
*********

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

Error response codes: 400, 404, 415


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
===================  ==========  ==============================================================

Response:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
commit_hash          string      commit_hash of tested repo
distro_hash          string      distro_hash of tested repo
success              boolean     whether the test was successful or not
job_id               string      name of the CI sending the vote
in_progress          boolean     is this CI job still in-progress?
timestamp            integer     timestamp for the repo
===================  ==========  ==============================================================


GET /api/repo_status
--------------------

Get all the CI reports for a specific repository.

Normal response codes: 200

Error response codes: 400, 404, 415


Request:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
commit_hash          string      commit_hash of the repo to fetch information for
distro_hash          string      distro_hash of the repo to fetch information for
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
url                  string      URL where to find additional information from the CI execution
timestamp            integer     Timestamp (in seconds since the epoch)
in_progress          boolean     False -> is this CI job still in-progress?
success              boolean     Was the CI execution successful?
notes                Text        Additional notes
===================  ==========  ==============================================================

GET /api/promotions
--------------------

Get all the promotions, optionally for a specific repository or promotion name.  The output
will be sorted by the promotion timestamp, with the newest first, and limited to 100 results
per query.

Normal response codes: 200

Error response codes: 400, 404, 415

Request:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
commit_hash          string      If set, commit_hash of the repo to use as filter key.
                     (optional)  Requires distro_hash.
distro_hash          string      If set, commit_hash of the repo to use as filter key.
                     (optional)  Requires commit_hash.
promote_name         string      If set to a value, filter results by the specified promotion
                     (optional)  name.
offset               integer     If set to a value, skip the initial <offset> promotions.
                     (optional)  
===================  ==========  ==============================================================

The JSON output will contain an array where each item contains:

==============  ==========  ==============================================================
Parameter         Type                             Description
==============  ==========  ==============================================================
commit_hash     string      commit_hash of the promoted repo
distro_hash     string      distro_hash of the promoted repo
promote_name    string      name used for the promotion
timestamp       integer     Timestamp (in seconds since the epoch)
==============  ==========  ==============================================================

The array will be sorted by the promotion timestamp, with the newest first.

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

Error response codes: 404, 415


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
===================  ==========  ==============================================================

Response:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
commit_hash          string      commit_hash of tested repo
distro_hash          string      distro_hash of tested repo
success              boolean     whether the test was successful or not
job_id               string      name of the CI sending the vote
in_progress          boolean     True -> is this CI job still in-progress?
timestamp            integer     Timestamp for this CI Vote (taken from the DLRN system time)
===================  ==========  ==============================================================


POST /api/report_result
-----------------------

Report the result of a CI job.

Normal response codes: 201

Error response codes: 400, 404, 415, 500

Request:

==============  ==========  ==============================================================
  Parameter       Type                             Description
==============  ==========  ==============================================================
job_id          string      name of the CI sending the vote
commit_hash     string      commit_hash of tested repo
distro_hash     string      distro_hash of tested repo
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
url             string      URL where to find additional information from the CI execution
timestamp       integer     Timestamp (in seconds since the epoch)
in_progress     boolean     False -> is this CI job still in-progress?
success         boolean     Was the CI execution successful?
notes           Text        Additional notes
==============  ==========  ==============================================================

POST /api/promote
-----------------

Promote a repository. This can be implemented as a local symlink creation in the DLRN
worker, or any other form in the future.

Note the API will refuse to promote using promote_name="consistent" or "current", since
those are reserved keywords for DLRN.

Normal response codes: 201

Error response codes: 400, 403, 404, 415, 500

Request:

==============  ==========  ==============================================================
  Parameter       Type                             Description
==============  ==========  ==============================================================
commit_hash     string      commit_hash of the repo to be promoted
distro_hash     string      distro_hash of the repo to be promoted
promote_name    string      name to be used for the promotion. In the current
                            implementation, this is the name of the symlink to be created
==============  ==========  ==============================================================

Response:

==============  ==========  ==============================================================
Parameter         Type                             Description
==============  ==========  ==============================================================
commit_hash     string      commit_hash of the promoted repo
distro_hash     string      distro_hash of the promoted repo
promote_name    string      name used for the promotion
timestamp       integer     Timestamp (in seconds since the epoch)
==============  ==========  ==============================================================

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
            Order deny,allow
            Allow from all
        </Directory>
    </VirtualHost>

Set ``CONFIG_FILE`` to the path of the DLRN configuration file, and make sure
you specify the right user and group for the ``WSGIDaemonProcess`` line.

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
