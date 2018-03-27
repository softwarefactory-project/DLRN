=======================================================================================
Scalable DLRN architecture, based on Zuul jobs with remote import on a central instance
=======================================================================================

Problem description
===================

The current DLRN architecture is monolithic, where a single process takes care
of three main activities:

* Refresh all git repositories for code and distgit, compute the list of
  commits to be built.
* Build each of the commits.
* Post-processing of the build result: create a new YUM repository, notify
  build errors via email/Gerrit, generate reports and synchronize YUM repos.

Some patches have been added to use multi-processing support for the git repo
refresh [1]_ and package builds [2]_, however they all retain the monolithic
approach, with a one-time execution, and all activities are executed on the
same system.

The current model has managed to work well for single package builds (e.g. for
CI use cases), and still works for larger enviroments, like [3]_. However,
there is room for improvement:

* The current one-time execution flow requires setting up a cron job to run
  DLRN on a fixed schedule.
* It is not easy to delegate activities to other systems, like package builds.
  Thus, scaling beyond the current limits is difficult to achieve.
* When multiple DLRN instances are running at once, the system gets a
  performance hit if more than one instance is refreshing the git
  repositories.

A new design is needed that complies with the following requirements:

* Keep the simple use case, with the same command-line, for the existing CI
  and single package build use case.
* Allow further scalability by providing multiple concurrent package builds,
  optionally on different systems.
* Avoid the need to execute DLRN on a fixed schedule. This would enable future
  work to refresh git repositories as a response to an external event, instead
  of a periodic pull.


Proposed change
===============

Overview
--------

The current DLRN flow is split into two parts: build jobs, that are executed
as a response to external events, and post-processing, which is done by a
central instance.

.. parsed-literal::

    
 +------------+
 |            |  Post  +-----------+
 | source git +------->|   Build   +----------+
 |            |        +-----------+          |
 +------------+                               |
                                              |
                                              |
                                              |       Remote import
 +------------+                               v           using    +--------+
 |            |  Post  +-----------+     +----+------+  DLRN API   |        |
 | distgit    +------->|   Build   +---->|  Publish  +------------>|  DLRN  |
 |            |        +-----------+     +----+------+             | server |
 +------------+                               ^                    |        |
                                              |                    +--------+
                                              |
                                              |
 +------------+                               |
 |            |  Post  +-----------+          |
 | rdoinfo    +------->|   Build   +----------+
 |            |        +-----------+
 +------------+


We have three different sources of change that will trigger a new build:

* A change in the source git repository.
* A change in the git repository containing the package definition (distgit).
* A change in rdoinfo, which adds a new package or changes the pinned source
  git tag/branch for an existing package.

Then, a publish job will take the results of the build (if successful), and
ask the central DLRN instance to import the generated RPMs using the remote
import API call [4]_.

For each of those sources of change, we need to create some specific
configuration in Zuul.

* For source git repositories, we will configure them using the Git driver
  [5]_, so it will poll the remote repository periodically.

* For distgit repositories and rdoinfo, we can use the Gerrit driver and work
  on its post events.

* The build job, defined in Zuul, will need to behave differently depending on
  the source of change, and also if the package is still under review or needs
  to be merged for a certain branch.

Alternatives
------------

* One alternative is to make a change in the DLRN architecture, and split its
  functions between different processes, which can then be distributed on more
  than one server. This option is being discussed in [6]_. The main advantage
  of using Zuul is that there is no need to change DLRN, and we can reuse the
  existing functionality in Zuul as a scheduler.

  On the flip side, since the logic and configuration is split between DLRN
  and several Zuul-based jobs, troubleshooting can be more complex in this
  architecture.

* A second alternative would be, for the current RDO Trunk use case, to setup
  individual worker machines for each builder. This would allow some level of
  horizontal scalability; however, if a single worker is overloaded there is
  still no way to scale other than vertically, by running multiple build
  processes.

Data model impact
-----------------

No impact is expected to the current data model.

Security Impact
---------------

Using the DLRN API to instruct the central instance to import a repository
requires using a set of credentials. We need to ensure that these credentials
are stored securely, for example using Zuul secrets [7]_. Also, jobs need to
be monitored to ensure these credentials cannot be leaked.

End User Impact
---------------

The existing command-line will be maintained, to ensure backwards
compatibility. Since no changes are planned to DLRN, no visible user impact
is expected.

Deployer Impact
---------------

Most of the impact is expected to be on the deployer side. We will need to
create:

* Automated jobs to build and publish, which take into account the different
  package statuses (under review, not available for certain branches, etc.).
  Note that this means shifting some of the DLRN logic to the Zuul jobs.

* Automated jobs to create the Zuul configuration for new packaging projects,
  similar to what is being done now in review.rdoproject.org [8]_.

* Additional monitoring/troubleshooting procedures, if needed, to cover cases
  where a build can silently be ignored for any reason (e.g. Zuul restart).

Developer Impact
----------------

None expected.

Implementation
==============

Assignee(s)
-----------

Primary assignee:
  jpena

Work Items
----------

* Create automated jobs to build and publish updated packages after each
  commit.

* Create automated jobs to propose changes in Zuul configuration following a
  new package addition to rdoinfo.

* Create standalone workers for targets that may be complex to automate, such
  as the current centos-master-head worker in RDO Trunk [9]_.

Dependencies
============

This architecture depends on some features that are unique to Zuul v3, so it
should only be built on an environment supporting it.

Due to the added complexity of this architecture, it should only be
implemented if the additional performance it provides is required. Otherwise,
the current standalone worker model may be a better fit for most environments.

Testing
=======

A prototype for this architecture has been successfully tested.

Since the implementation of this architecture in production can be disruptive,
it is advised to test the Zuul jobs using a parallel DLRN instances during
some time before switching over.

Documentation Impact
====================

This architecture is an implementation choice, so it should be documented by
the environment that selects it (e.g. review.rdoproject.org). This document
outlines the basic design concepts.

References
==========

 .. [1] Use multiple processes for git clone
    https://softwarefactory-project.io/r/8695

 .. [2] Parallel mock builds in DLRN
    https://github.com/softwarefactory-project/DLRN/commit/298f639c9f07992790c42a0b0d9852ae34cbfcdf

 .. [3] RDO Trunk repositories, built by DLRN
    https://trunk.rdoproject.org

 .. [4] DLRN remote import functionality
    https://github.com/softwarefactory-project/DLRN/commit/976fd76ae5fee0d814b3c9b2e979816c3e564cd9

 .. [5] Zuul Git driver documentation
    https://github.com/openstack-infra/zuul/blob/master/doc/source/admin/drivers/git.rst

 .. [6] New spec: DLRN architecture with scheduler and worker processes
    https://softwarefactory-project.io/r/10653

 .. [7] Creating secrets in Zuul v3
    https://docs.openstack.org/infra/zuul/user/encryption.html

 .. [8] Create projects in review.rdoproject.org after an rdoinfo change
    https://github.com/rdo-infra/review.rdoproject.org-config/blob/849aa0dde65ad66506a63f71e8a9077c3d358a72/jobs/rdoinfo.yaml#L203-L239

 .. [9] RDO Trunk centos-master-head worker
    https://trunk.rdoproject.org/centos7-master-head/status_report.html
