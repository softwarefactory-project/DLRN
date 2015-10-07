========
Usage
========

Parameters
----------

.. code-block:: console

    usage: delorean [-h] --config-file CONFIG_FILE [--info-repo INFO_REPO]
                    [--build-env BUILD_ENV] [--local] [--head-only]
                    [--package-name PACKAGE_NAME] [--dev] [--log-commands]
                    [--use-public] [--order]
    
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
      --log-commands        Log the commands run by delorean.
      --use-public          Use the public master repo for dependencies when doing
                            install verification.
      --order               Compute the build order according to the spec files
                            instead of the dates of the commits.


Initial build
-------------

Some of the projects require others to build. As a result, use the
special option ``--order`` to build in the order computed from the
BuildRequires and Requires fields of the spec files. If this option is
not specified, Delorean builds the packages in the order of the
timestamps of the commits.

.. code-block:: shell-session

    $ delorean --config-file projects.ini --order

Output and log files
--------------------

The output of Delorean is generated in the ``<datadir>/repos`` directory. It consists
of the finished ``.rpm`` files for download, located in ``/repos/current``, and reports
of the failures in ``/repos/status_report.html``, and a report of all builds in
``/repos/report.html``.
