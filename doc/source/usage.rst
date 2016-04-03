========
Usage
========

Parameters
----------

.. code-block:: console

    usage: dlrn [-h] --config-file CONFIG_FILE [--info-repo INFO_REPO]
                [--build-env BUILD_ENV] [--local] [--head-only]
                [--package-name PACKAGE_NAME] [--dev] [--log-commands]
                [--use-public] [--order] [--status] [--recheck] [--version]
                [--run RUN] [--stop]
    arguments:
      -h, --help            show this help message and exit
      --config-file CONFIG_FILE
                            Config file (required)
      --info-repo INFO_REPO
                            use a local rdoinfo repo instead of fetching the
                            default one using rdopkg.
      --build-env BUILD_ENV
                            Variables for the build environment.
      --local               Use local git repos if possible
      --head-only           Build from the most recent Git commit only.
      --package-name PACKAGE_NAME
                            Build a specific package name only.
      --dev                 Don't reset packaging git repo, force build and add
                            public master repo for dependencies (dev mode).
      --log-commands        Log the commands run by DLRN.
      --use-public          Use the public master repo for dependencies when doing
                            install verification.
      --order               Compute the build order according to the spec files
                            instead of the dates of the commits.
      --version             show program's version number and exit
      --run RUN             Run a program instead of trying to build. Imply
                            --head-only
      --stop                Stop on error.



Initial build
-------------

Some of the projects require others to build. As a result, use the
special option ``--order`` to build in the order computed from the
BuildRequires and Requires fields of the spec files. If this option is
not specified, DLRN builds the packages in the order of the
timestamps of the commits.

.. code-block:: shell-session

    $ dlrn --config-file projects.ini --order


Run DLRN
--------

Run DLRN for the package you are trying to build.

.. code-block:: shell-session

    $ dlrn --config-file projects.ini --local --package-name openstack-cinder

This will clone the packaging for the project you’re interested in into ``data/openstack-cinder_repo``,
you can now change this packaging and rerun the DLRN command in test your changes.

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
