==================================================================================================
New DLRN architecture, based on a multi-process model with separate scheduler and worker processes
==================================================================================================

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
* Allow each activity to run continuously, as a daemon, without a need for
  a cron job to execute DLRN on a fixed schedule. This would enable future
  work to refresh git repositories as a response to an external event,
  instead of a periodic pull.

Proposed change
===============

Overview
--------

The current DLRN flow is split into its three main activities, with
coordination between activities happening via message queues created using
ZeroMQ [4]_.

.. parsed-literal::

                          +--------+
                   +----->| Worker +------+
                   |      +--------+      |
                   |                      |
                   |      +--------+      |
                   +----->| Worker +------+
                   |      +--------+      |
                   |                      |
    +-----------+  |                      |         +--------------+
    | Scheduler |--+         ...          +-------->| Repo-Manager |
    +-----------+  |                      |         +--------------+
                   |                      |
                   |                      |
                   |      +--------+      |
                   +----->| Worker +------+
                          +--------+

* The **scheduler** activity will refresh the git repositories, compute the
  list of commits to be built, and send one message for each commit to a PUSH
  ZeroMQ socket, detailing the commit to be built.
* The **worker** process will receive the commit information from a PULL
  socket, build the package, and send the results to a PUSH socket connected
  to the repo manager.
* The **repo manager** process will receive the results from a PULL socket,
  create a YUM repository with the newly built package, and perform all
  required post-build actions.

Alternatives
------------

* One alternative is to use a Zuul-based architecture, where a post job is
  executed after each commit to the code or distgit repository is merged. This
  job would build the package, and then use existing DLRN import functionality
  [5]_ to send the packages to a central instance. This requires a large
  amount of work to set up the post jobs for all projects managed by the DLRN
  instance, and different drivers to ensure that projects not managed by a
  Gerrit instance are covered.

* A second alternative would be, for the current RDO Trunk use case, to setup
  individual worker machines for each builder. This would allow some level of
  horizontal scalability; however, if a single worker is overloaded there is
  still no way to scale other than vertically, by running multiple build
  processes.

* For the message passing between the three components, we could use a
  different broker, like ActiveMQ or RabbitMQ. However, this would require an
  additional piece of infrastructure to manage, and we do not expect DLRN to
  scale to that extent in the short term. Thus, a simpler approach is
  advisable.

Data model impact
-----------------

No impact is expected to the current data model.

Security Impact
---------------

For the local use case, we will ensure the domain sockets created by ZeroMQ
when using the local inter-process [6]_ transport use the right permissions.

Once the distributed use case is implemented, with connections via TCP
sockets, a more secure paradigm will need to be used. ZeroMQ provides
encryption and authentication support [7]_, so it will be used in the
implementation.

End User Impact
---------------

The existing command-line will be maintained, to ensure backwards
compatibility. When the current command-line is used, DLRN will:

* Create a single scheduler process, which may still use multiprocessing to
  refresh git repositories in parallel.
* Create one or multiple worker processes, as defined in the ``workers``
  option in ``projects.ini``.
* Create a single repo manager process.
* Use the ZeroMQ local inter-process [6]_ transport for communication between
  the processes.

Three new command-line utilities will be created, for the distributed use
case:

* **dlrn-scheduler**
* **dlrn-worker**
* **dlrn-repo-manager**

They will implement each of the three activities. There will only be one
dlrn-scheduler and dlrn-repo-manager per setup, but multiple dlrn-workers can
be started.

Deployer Impact
---------------

Initially, no impact is expected, as backwards compatibility will be assured.

If a distributed deployment is required, the deployer will need to ensure that
the proper configuration is created, including correct ``project.ini`` files
and ZeroMQ connections using unused TCP ports.

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

* Create initial implementation with 3 processes on the same system, with
  local inter-process communication.
* Create new command-line utilities as daemons, still using local
  inter-process communication.
* Add support in the DLRN repo manager to get the RPMs from an external
  location, based on the current DLRN remote import code.
* Extend support for the distributed use case, with TCP-based communication.

Dependencies
============

The new implementation will likely require long-lived database connections for
some components. We should make the changes depend on the DLRN database access
refactor [8]_, since it fixes some known issues when accessing external
databases.

Testing
=======

Unit tests will be created for the new functionality. The existing functional
tests will ensure that current functionality is not broken in the process.

Documentation Impact
====================

The new architecture will be described in the ``internals.rst`` document.
Also, user documentation to explain how to configure and operate a distributed
environment will be created.

References
==========

 .. [1] Use multiple processes for git clone
    https://softwarefactory-project.io/r/8695

 .. [2] Parallel mock builds in DLRN
    https://github.com/softwarefactory-project/DLRN/commit/298f639c9f07992790c42a0b0d9852ae34cbfcdf

 .. [3] RDO Trunk repositories, built by DLRN
    https://trunk.rdoproject.org

 .. [4] ZeroMQ
    http://zeromq.org/

 .. [5] Add functionality to import commits built by another instance
    https://github.com/softwarefactory-project/DLRN/commit/976fd76ae5fee0d814b3c9b2e979816c3e564cd9

 .. [6] ZeroMQ local inter-process communication transport
    http://api.zeromq.org/2-1:zmq-ipc

 .. [7] ZeroMQ encryption
    http://zeromq.org/topics:encryption

 .. [8] Refactor DB usage
    https://softwarefactory-project.io/r/9244
