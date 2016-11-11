######################
API definition (draft)
######################

*******************
General information
*******************

``GET`` operations will be non-authenticated. ``POST`` operations will require authentication using username+password.

All data will be sent/received using JSON objects, unless stated otherwise.

*********
API calls
*********

POST /api/report_result
-----------------------

Report result of a CI job, and optionally create a symlink.

Normal response codes: 201

Error response codes: 400, 404, 415

Request:

==============  ==========  ==============================================================
  Parameter       Type                             Description
==============  ==========  ==============================================================
link_name       string      name of the CI sending the vote
commit_hash     string      commit_hash of tested repo
distro_hash     string      distro_hash of tested repo
url             string      URL where to find additional information from the CI execution
timestamp       integer     Timestamp (in seconds since the epoch)
success         boolean     Was the CI execution successful?
create_symlink  boolean     Create symlink (optional, by default it's False)
notes           Text        Additional notes (optional)
==============  ==========  ==============================================================

Response:

==============  ==========  ==============================================================
Parameter         Type                             Description
==============  ==========  ==============================================================
link_name       string      name of the CI sending the vote
commit_hash     string      commit_hash of tested repo
distro_hash     string      distro_hash of tested repo
url             string      URL where to find additional information from the CI execution
timestamp       integer     Timestamp (in seconds since the epoch)
in_progress     boolean     False -> is this CI job still in-progress?
success         boolean     Was the CI execution successful?
create_symlink  boolean     Symlink created or not
notes           Text        Additional notes
==============  ==========  ==============================================================

POST /api/get_last_tested_repo
------------------------------

Get the last tested repo since a specific timestamp (optionally for a CI job), and add an "in progress" entry in the CI job table for this . If no repo is found in the specified timeframe, the last "consistent" repo is returned [1].


Normal response codes: 201

Error response codes: 404, 415


Request:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
timestamp            integer     Timestamp (in seconds since the epoch) we want to use as the
                                 base for the search. Any repo tested or being tested after
                                 that timestamp will be considered.
reporting_link_name  string      Name of the CI that will add the "in progress" entry in the CI
                                 job table
success              boolean     If set to a value, find repos with a successful/unsuccessful
                     (optional)  vote (as specified). If not set, any tested repo will be
                                 considered.
link_name            string      name of the CI that sent the vote. If not set, no filter will
                     (optional)  be set on CI.
===================  ==========  ==============================================================

Response:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
commit_hash          string      commit_hash of tested repo
distro_hash          string      distro_hash of tested repo
success              boolean     whether the test was successful or not
link_name            string      name of the CI sending the vote
in_progress          boolean     True -> is this CI job still in-progress?
timestamp            integer     Timestamp for this CI Vote (taken from the DLRN system time)
===================  ==========  ==============================================================

[1] That means we need to store consistent repos in the DB. It could be like a phase 0 CI, and stored in the CIVote table.


GET /api/get_last_tested_repo
-----------------------------

Get the last tested repo since a specific timestamp. If a link_name is specified, get the last tested repo for that timestamp for that CI job. If no repo is found in the specified timeframe, the last "consistent" repo is returned.


    NOTE(apevec): any real in-progress CIVote should get precedance over newer consistent otherwise CIs will not converge (consistent will advance faster)


Normal response codes: 200

Error response codes: 400, 404, 415


Request:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
timestamp            integer     Timestamp (in seconds since the epoch) we want to use as the
                                 base for the search. Any repo tested or being after that
                                 timestamp will be considered.
success              boolean     If set to a value, find repos with a successful/unsuccessful
                     (optional)  vote (as specified). If not set, any tested repo will be
                                 considered.
link_name            string      name of the CI that sent the vote. If not set, no filter will
                     (optional)  be set on CI.
===================  ==========  ==============================================================

Response:

===================  ==========  ==============================================================
       Parameter       Type                             Description
===================  ==========  ==============================================================
commit_hash          string      commit_hash of tested repo
distro_hash          string      distro_hash of tested repo
success              boolean     whether the test was successful or not
link_name            string      name of the CI sending the vote
in_progress          boolean     is this CI job still in-progress?
timestamp            integer     timestamp for the repo
===================  ==========  ==============================================================
