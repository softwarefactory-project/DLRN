========
Usage
========

Parameters
----------

.. code-block:: console

    usage: dlrn [-h] [--config-file CONFIG_FILE]
                [--config-override CONFIG_OVERRIDE] [--info-repo INFO_REPO]
                [--build-env BUILD_ENV] [--local] [--head-only]
                [--project-name PROJECT_NAME | --package-name PACKAGE_NAME]
                [--dev] [--log-commands] [--use-public] [--order] [--sequential]
                [--status] [--recheck] [--force-recheck] [--version] [--run RUN]
                [--stop] [--verbose-build] [--no-repo] [--debug]

    optional arguments:
      -h, --help            show this help message and exit
      --config-file CONFIG_FILE
                            Config file. Default: projects.ini
      --config-override CONFIG_OVERRIDE
                            Override a configuration option from the config file.
                            Specify it as: section.option=value. Can be used
                            multiple times if more than one override is needed.
      --info-repo INFO_REPO
                            use a local rdoinfo repo instead of fetching the
                            default one using rdopkg. Only applies when
                            pkginfo_driver is rdoinfo in projects.ini
      --build-env BUILD_ENV
                            Variables for the build environment.
      --local               Use local git repos if possible. Only commited changes
                            in the local repo will be used in the build.
      --head-only           Build from the most recent Git commit only.
      --project-name PROJECT_NAME
                            Build a specific project name only. Use multiple times
                            to build more than one project in a run.
      --package-name PACKAGE_NAME
                            Build a specific package name only. Use multiple times
                            to build more than one package in a run.
      --dev                 Don't reset packaging git repo, force build and add
                            public master repo for dependencies (dev mode).
      --log-commands        Log the commands run by dlrn.
      --use-public          Use the public master repo for dependencies when doing
                            install verification.
      --order               Compute the build order according to the spec files
                            instead of the dates of the commits. Implies
                            --sequential.
      --sequential          Run all actions sequentially, regardless of the number
                            of workers specified in projects.ini.
      --status              Get the status of packages.
      --recheck             Force a rebuild for a particular package. Implies
                            --package-name
      --force-recheck       Force a rebuild for a particular package, even if its
                            last build was successful. Requires setting
                            allow_force_rechecks=True in projects.ini. Implies
                            --package-name and --recheck
      --version             show program's version number and exit
      --run RUN             Run a program instead of trying to build. Implies
                            --head-only
      --stop                Stop on error.
      --verbose-build       Show verbose output during the package build.
      --no-repo             Do not generate a repo with all the built packages.
      --debug               Print debug logs



Quickstart single package build
-------------------------------

Run DLRN for the package you are trying to build.

.. code-block:: shell-session

    $ dlrn --use-public --package-name openstack-cinder

By using the parameter ``--use-public`` DLRN will configure the build
environment to use the public master repository.

In case of failure you might need to re-run a build by discarding the
DLRN database content. To do so you need to run:

.. code-block:: shell-session

    $ dlrn --recheck --package-name openstack-cinder
    $ dlrn --use-public --package-name openstack-cinder

It is also possible to force the recheck of a successfully built commit.
Please note that this is not advisable if you rely on the DLRN-generated
repositories, since it will remove packages that other hashed repositories
may have symlinked.

If you are sure you need it, set ``allow_force_rechecks=true`` in your
projects.ini file, then run:

.. code-block:: shell-session

    $ dlrn --recheck --force-recheck --package-name openstack-cinder
    $ dlrn --use-public --package-name openstack-cinder

Full build
----------

Some of the projects require others to build. As a result, use the
special option ``--order`` to build in the order computed from the
BuildRequires and Requires fields of the spec files. If this option is
not specified, DLRN builds the packages in the order of the
timestamps of the commits.

.. code-block:: shell-session

    $ dlrn --order


Advanced single package build
-----------------------------

Run DLRN for the package you are trying to build.

.. code-block:: shell-session

    $ dlrn --local --package-name openstack-cinder

This will clone the packaging for the project you’re interested in into ``data/openstack-cinder_repo``,
you can now change this packaging and rerun the DLRN command in test your changes.

This command expects build and runtime dependencies to be found in previously
built repositories (during the initial full build).

If you have locally changed the packaging make sure to include ``--dev`` in the command line.
This switches DLRN into **dev mode** which causes it to preserve local changes to your
packaging between runs so you can iterate on spec changes. It will also cause the most current
public master repository to be installed in your build image(as some of its contents will be
needed for dependencies) so that the packager doesn’t have to build the entire set of packages.


Output and log files
--------------------

The output of DLRN is generated in the ``<datadir>/repos`` directory. It consists
of the finished ``.rpm`` files for download, located in ``/repos/current``, and reports
of the failures in ``/repos/status_report.html``, and a report of all builds in
``/repos/report.html``.

Importing commits built by another DLRN instance
------------------------------------------------

DLRN has the ability to import a commit built by another instance. This allows a master-worker
architecture, where a central instance aggregates builds made by multiple, possibly short-lived
instances.

The builder instance will be invoked as usual, and it will output a ``commit.yaml`` file in the
generated repo. In general, we will want to use the ``--use-public`` command-line option to make
sure all repos are available. Note it is very important to **not use** the ``--dev`` command-line
option, as some of the commit metadata will be lost, specifically all data related to the distgit
repository.

On the central instance side, the ``dlrn-remote`` has the following syntax:

.. code-block:: console

    usage: dlrn-remote [-h] [--config-file CONFIG_FILE] --repo-url REPO_URL [--info-repo INFO_REPO]

    arguments:
      -h, --help            show this help message and exit
      --config-file CONFIG_FILE
                            Config file. Default: projects.ini
      --repo-url REPO_URL   Base repository URL for remotely generated repo
                            (required)
      --info-repo INFO_REPO
                            use a local rdoinfo repo instead of fetching the
                            default one using rdopkg. Only applies when
                            pkginfo_driver is rdoinfo in projects.ini

An example command-line would be:

.. code-block:: console

    $ dlrn-remote --config-file projects.ini \
      --repo-url http://<builder IP>/repos/<hash>/

Where ``http://192.168.122.164/repos/<hash>`` is the URL where the builder instance exports
its built repo. The ``commit.yaml`` file must be on the same hashed repo, as created by DLRN.

Purging old commits
-------------------

Over time, the disk space consumed by DLRN will grow, as older commits and their repositories
are never removed. It is possible to use the ``dlrn-purge`` command to purge commits built before
a certain date.

.. code-block:: console

    usage: dlrn-purge [-h] --config-file CONFIG_FILE --older-than OLDER_THAN [-y] [--dry-run]
    arguments:
      -h, --help            show this help message and exit
      --config-file CONFIG_FILE
                            Config file (required)
      --older-than  OLDER_THAN
                            how old a build needs to be, in order to be considered
                            for removal (required). It is measured in days.
      -y                    Assume yes for all questions.
      --dry-run             If specified, do not apply any changes. Instead, show what would
                            be removed from the filesystem.

Old commits will remain in the database, although their flag will be set to purged, and their
associated repo directory will be removed. There is one exception to this rule, when an old
commit is the newest one that was successfully built. In that case, it will be preserved.

Building only the last commit
-----------------------------

You can use the ``--head-only`` option to build only the last commit of
the branch for all the projects or a particular project
using ``--project-name`` or ``--package-name``.

Doing so you skip commits and if you find a problem in the last
commit, you can use the ``./scripts/bisect.sh`` helper to drive a ``git
bisect`` session to find which commit has caused the problem:

.. code-block:: console

   Usage: ./scripts/bisect.sh <dlrn config file> <project name> <good sha1> <bad sha1> [<dlrn extra args>]
