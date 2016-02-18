============
Repositories
============

Delorean doesn't stop at building packages, it also generates yum repositories
you can install the packages from.

Delorean repositories are all hosted on http://trunk.rdoproject.org.

This documentation goes through the various repositories and what they are
used for.

Building new packages and repositories
--------------------------------------
Delorean watches upstream git repositories for new commits. When there is one,
Delorean builds a new version of the project's package with the new commit.

On a successful build, Delorean will generate a new repository with the latest
version of every package that successfully built.

A package build can fail due to different reasons, for example when a new
dependency was introduced that needs to be added to the RPM spec file.
If there is a build failure, no repository is generated and the project's
package is not updated.

The package will not be updated for as long as it fails to build.
This means that newer repositories generated from other projects' commits would
not contain all the latest commits of the project that failed to build.

Delorean does not delete any generated repositories. This means we can use any
previously built repositories if necessary.

Generated repositories are unique and each have their own hash.
For example, you might be using the Delorean ``/centos7/current/delorean.repo``
repository but in fact this corresponds to
``/centos7/42/0c/420c638d6325d1ccf50eb5fe430c5d255dcbfb94_52cbbfe7``.

Delorean manages these references as simple symbolic links for the ``current``
and ``consistent`` repositories. The ``current-passed-ci`` repository is a
symbolic link managed automatically by RDO's continuous integration pipeline
and is not managed or known by Delorean itself.

Delorean repository: delorean-deps
----------------------------------
OpenStack projects are typically built into the Delorean repositories.
These projects require dependencies that Delorean does not build, for example
python-requests, python-prettytable and so on.

The RDO project provides a mirror which contains all of these dependencies and
the repository configuration is available at ``/delorean-deps.repo`` for each
release.

For example:

* Trunk: http://trunk.rdoproject.org/centos7/delorean-deps.repo
* Liberty: http://trunk.rdoproject.org/centos7-liberty/delorean-deps.repo

Delorean repository: current
----------------------------
On a successful build, Delorean will generate a new repository with the latest
version of every package that successfully built.

This new repository will be tagged as ``current``.

A Delorean current repository might not contain all the latest upstream commits
if there are any ongoing build failures that are unresolved.

This repository is available at ``/current/delorean.repo`` for each release.

For example:

* Trunk: http://trunk.rdoproject.org/centos7/current/delorean.repo
* Liberty: http://trunk.rdoproject.org/centos7-liberty/current/delorean.repo

Delorean repository: consistent
-------------------------------
Delorean ``consistent`` repositories are generated for any given set of
packages that have no current build failures.

These repositories have the latest and greatest of every package and all
upstream commits have been successfully built up until that point.

The continuous integration done to test RDO packages target the Delorean
consistent repositories.

This repository is available at ``/consistent/delorean.repo`` for each release.

For example:

* Trunk: http://trunk.rdoproject.org/centos7/consistent/delorean.repo
* Liberty: http://trunk.rdoproject.org/centos7-liberty/consistent/delorean.repo

Delorean repository: current-passed-ci
--------------------------------------
The RDO project has a continuous integration pipeline that consists of multiple
jobs that deploy and test OpenStack as accomplished by different installers.

This vast test coverage attempts to ensure that there are no known issues
either in packaging, in code or in the installers themselves.

Once a Delorean consistent repository has undergone these tests successfully,
it will be promoted to ``current-passed-ci``.

current-passed-ci represents the latest and greatest version of RDO trunk
packages that were tested together successfully.

We encourage installer projects and users of RDO to use this repository to
keep up with trunk while maintaining a certain level of stability provided by
RDO's CI.

This repository is available at ``/current-passed-ci/delorean.repo`` for each
release.

For example:

* Trunk: http://trunk.rdoproject.org/centos7/current-passed-ci/delorean.repo
* Liberty:
  http://trunk.rdoproject.org/centos7-liberty/current-passed-ci/delorean.repo
