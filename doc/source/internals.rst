==============
DLRN internals
==============

This document aims at describing the inner workings of DLRN, so a new
contributor can get up to speed as quickly as possible.

*************
Main concepts
*************

The following basic concepts are used in DLRN. You'll need to get used to them
if you want to understand the code:

- **Source Git**: DLRN will always take the source code to build the package from a
  Git repository, regardless of the ``Source0`` entry in the spec file.

- **Distgit**: spec files are assumed to be present in a Git repository. DLRN has a
  driver-based mechanism to allow different options for the distgit location,
  see the `Package Info Drivers`_ section.

- **Project**: each project corresponds with a package to be built. A package may
  define a number of subpackages in the spec file, but a single source RPM file
  is always created. The DLRN driver mechanism allows us to have different
  sources of information for the project list, such as
  `rdoinfo <https://github.com/redhat-openstack/rdoinfo>`_ or a single git
  repo.

- **Commit**: a commit is the main abstraction used by DLRN. It aggregates all
  information related to each package built, such as:

  - Project name
  - Hash of the commit from the source git
  - Hash of the commit from the distgit
  - Build status (successful or not)
  - Name of the rpms

*******************
Directory structure
*******************

The DLRN codebase is structured as follows:

- **doc/**: project documentation
- **scripts/**: several useful scripts, used by CI and DLRN itself, plus some other
  miscellaneous files.

  * *build_rpm.sh*: script that calls mock to build rpm files (see the
    `Building packages`_ section).
  * *submit_review.sh*: script to open a Gerrit review after a build failure (see
    the `Error reporting`_ section).
  * *centos.cfg*, *centos8.cfg*, *fedora.cfg* and *redhat.cfg*: base mock
    configurations for  CentOS 7, CentOS 8, Fedora and RHEL 8 builders. For a RHEL 8
    builder, you will have to make sure the appropriate base repos are configured,
    since those are not publicly available. These base configurations can be located
    in a separate directory, defined by the ``configdir`` option in projects.ini.

- **dlrn/**: main DLRN code

  * *build.py*: build functions, described in detail in the `Building packages`_
    section.
  * *config.py*: general configuration management.
  * *db.py*: database-related code.
  * *notifications.py*: error reporting functions.
  * *purge.py*: dlrn-purge command, used to reduce the disk usage on long-running
    instances.
  * *reporting.py*: reporting functions, create simple HTML reports of the
    repository status.
  * *repositories.py*: functions required to clone a git repo and get information
    from it.
  * *rpmspecfile.py*: basic rpm spec file parsing to be able to get package names
    and dependencies.
  * *rsync.py*: synchronizes yum repositories between servers, used to have a
    multi-node architecture.
  * *shell.py*: main file, reads command-line arguments and launches the build
    process.
  * *utils.py*: miscellaneous utilities.
  * **api/**: DLRN API code, described in detail in `its own <api.html>`_ page.
  * **drivers/**: modular drivers for project listing and distgit location,
    described in the `Package Info Drivers`_ section. We are also including modular
    drivers for different build methods.
  * **migrations/**: Alembic scripts for database maintenance.
  * **stylesheets/**: contains a CSS file used by the reporting module.
  * **templates/**: contains Jinja2 templates, also used by the reporting module.
  * **tests/**: unit tests.

********************
High level algorithm
********************

When DLRN is run, the following (simplified) sequence of events is executed:

.. code-block:: none

    fetch information for available projects
    for each project
        find last processed commit
        refresh source git
        find last commit in source git and distgit
        if any commit is later than last_processed_commit
            add commit to list of commits to be processed
    for each commit_to_be_processed
        build package
        create yum repo with built package and the latest versions of every other package
        if errors
            report via e-mail or Gerrit review if configured
        store commit in DB
        generate HTML report

*************
Configuration
*************

DLRN uses a simple INI file for its configuration. Most config options are
located in the ``[DEFAULT]`` section and read during startup. Only
driver-specific options have their own section.

The dlrn/config.py file defines a ``ConfigOptions`` class, that will create an
object including all parsed options.

********************
Package Info Drivers
********************

Package info drivers are derived from the ``PkgInfoDriver`` class
(see dlrn/drivers/pkginfo.py), and are used to:

- Define a list of projects (packages) to be built
- Define the source and distgit repos for each project
- Fetch the new commits for each project's source and distgit repos
- Pre-process spec files, if needed

Each driver must provide the following methods:

- **getpackages()**. This method will return a list of dictionaries. Each
  individual dict must contain the following mandatory keys (others are
  optional):

  - 'name': package name
  - 'upstream': URL for source repo
  - 'master-distgit': URL for distgit repo
  - 'maintainers': list of e-mail addresses for package maintainers

- **getinfo()**. This method will return a list of commits to be processed for a
  specific package.

- **preprocess()**. This method will run any required pre-processing for the
  spec files. If the ``custom_preprocess`` variable is defined in ``projects.ini``,
  the external program(s) or script(s) defined in the variable will be executed as
  the last step of the pre-processing.

- **distgit_dir()**. This method will return the distgit repo directory for a
  given package name.

You can check the code of the existing
`rdoinfo driver <https://github.com/softwarefactory-project/DLRN/blob/master/dlrn/drivers/rdoinfo.py>`_
and `gitrepo driver <https://github.com/softwarefactory-project/DLRN/blob/master/dlrn/drivers/gitrepo.py>`_
to see their implementation specifics. If you create a new driver, you
need to add the project name to the ``projects.ini`` configuration file, and
if you need any new options, be sure to add them to a driver-specific section
(see the `Configuration`_ section for details).

*********************
Package Build Drivers
*********************

Package build drivers are derived from the ``BuildRPMDriver`` class
(see dlrn/drivers/buildrpm.py), and are used to perform the actual package
build from an SRPM file.

Each driver must provide the following method:

- **build_package** This method will take an output directory, where the SRPM
  is located, and build it using the driver-specific method.

You can check the code of the existing
`mock <https://github.com/softwarefactory-project/DLRN/blob/master/dlrn/drivers/mockdriver.py>`_
driver to see its implementation specifics. If you create a new driver, you
need to add the project name to the ``projects.ini`` configuration file, and
if you need any new options, be sure to add them to a driver-specific section
(see the `Configuration`_ section for details).

*****************
Building packages
*****************

The package build logic is included in build.py. There we have several
functions:

- **build()**. This is the function called externally. It gathers some
  configuration options and parameters, then calls ``build_rpm_wrapper`` to
  launch the build process and returns a list with the built rpms.

- **build_rpm_wrapper()**. This wrapper function prepares the mock configuration
  file to be used during the build using the configuration. It will also add
  the most current repository to the mock configuration, so we can use packages
  in the current repository as dependencies during the build. Then, it will
  spawn a Bash script, ``build_srpm.sh`` to build the source RPM, and call the
  appropriate build driver to generate the binary RPM.

The ``build_srpm.sh`` script takes care of creating the source RPM. Some magic is
required to build it, specifically:

- The script tries to determine a version and release number for the package.
  This version number should be compatible with the
  `Fedora guidelines <https://fedoraproject.org/wiki/Packaging:Versioning>`_,
  and allow upgrades **from** and **to** packages from stable releases, which is
  not always easy. We use the following algorithm:

  * For Python projects, take the output from ``python setup.py --version``.
    Most OpenStack projects use PBR, which gives us proper pre-versioning after a
    tagged release.
  * For Puppet projects, we take the version from the ``metadata.json`` or
    ``Modulefile`` files, if available, and increase the .Z version if there are
    any commits after the tagged release.
  * For other projects, we take the version number from the latest git tag.
  * If everything fails, default to version 0.0.1.
  * The release number is always 0.<date>.<upstream source commit short hash>.

- A tarball is generated using ``python setup.py sdist`` for Python projects,
  ``gem build`` for Ruby gems, and tar for any other project. Then, the spec file
  is updated to use this tarball as ``Source0``, and a source RPM is created.

The binary RPM is built from the SRPM using a the build driver specified in
``projects.ini``. This can be done using Mock, Copr, Brew, or any other tool,
provided that the required driver is available.

***********************
Hashed yum repositories
***********************
Each build is stored on a separate directory. A hashed structure is used for the
directories, such as ``cd/af/cdaf2c77d974d5e794909313dceb3554be69a42e_4b1619fe``.
In this structure, ``cdaf2c77d974d5e794909313dceb3554be69a42e`` is the commit hash
for the source git repo, and ``4b1619fe`` is the short hash for the distgit commit.
The first two directory levels (``cd/af``) are taken from the commit hash.

*****************
Component support
*****************

DLRN now supports the concept of *components* inside a repository. We can use
components to divide the packages in a repo into logical aggregations. For example,
in the OpenStack use case, we could have separate components for those packages
related to networking, compute, storage, etc.

Currently, only the ``RdoInfoDriver`` and ``DownstreamInfoDriver`` package info
drivers supports this. When components are defined, and enabled with the
``use_components=True`` option in ``projects.ini``, DLRN will change its behavior
in the following ways:

- Hashed yum repositories will change their paths, including a component part. For
  example, a commit for a package in the compute component will use hash
  ``component/compute/cd/af/cdaf2c77d974d5e794909313dceb3554be69a42e_4b1619fe``.
- Each component will have a separate repository (``component/compute``,
  ``component/network``and so on), and the ``current`` and ``consistent`` symlinks
  will also be relative to each component.
- To preserve compatibility with instances without component support, the top-level
  ``current`` and ``consistent`` symlinks will be replaced by a ``current`` and
  ``consistent`` directory. Each directory will contain a single .repo file, and
  that file will aggregate the .repo files for the current/consistent repositories
  of all components.

******************
Post-build actions
******************

After a package is built, we need to create a package repository with the latest
version for every package in the project list. The ``post_build()`` function in
``shell.py`` takes care of that. The idea behind this is that the repo for each
build will contain the most current version of each package to date. This
behavior can be skipped if the ``--no-repo`` command-line option is provided, so
only the build package and logs will be stored.

To minimize the amount of storage used for each repo, DLRN does not copy the
packages to the current hashed directory. Instead, ``post_build()`` iterates
through the list of packages, finding the RPMs for their latest successful
builds, and symlinks them in the current hashed directory.

It is probably easier to understand with an example:

- Initially, we only have source commit 010b0a and distgit commit 020202 for
  project foo, then its hashed repo will look like:

  .. code-block:: bash

     01/0b/010b0a_020202/foo-<version>.el7.centos.noarch.rpm

- Then, we build project bar, with source commit 030303 and distgit
  commit 040404. Its hashed repo will be:

  .. code-block:: bash

     03/03/030303_040404/bar-<version>.el7.centos.noarch.rpm
     03/03/030303_040404/foo-<version>.el7.centos.noarch.rpm -> ../../../01/0b/010b0a_020202/foo-<version>.el7.centos.noarch.rpm

  And the same process will be followed for every new package.

***************
Error reporting
***************

DLRN allows two different ways to notify build errors, both included in
notifications.py:

- A notification e-mail, sent using the ``sendnotifymail()`` function. The mail
  recipient list is taken from the ``maintainers`` project property.
- A Gerrit review. This option makes use of a utility script
  ``submit_review.sh`` and the configured options in options.ini to create the
  review. It also adds the project maintainers to the generated review.

*************
API internals
*************

The API is described in detail in `its own <api.html>`_ documentation.
