========
Usage
========

Parameters
----------

usage: delorean [-h] --config-file CONFIG_FILE --info-file INFO_FILE
                [--build-env BUILD_ENV] [--local] [--head-only]
                [--package-name PACKAGE_NAME] [--dev]

arguments:
  -h, --help            show this help message and exit
  --config-file CONFIG_FILE
                        Config file (required)
  --info-file INFO_FILE
                        Package info file (required)
  --build-env BUILD_ENV
                        Variables for the build environment.
  --local               Use local git repos if possible
  --head-only           Build from the most recent Git commit only.
  --package-name PACKAGE_NAME
                        Build a specific package name only.
  --dev                 Don't reset packaging git repo, force build and add
                        public master repo for dependencies (dev mode).


Initial build failures
----------------------

In order to build some of the projects you need to have others already built. As a result the first
build of some projects may fail. The simplest solution at the moment is to allow this to happen,
delete the record of the failed builds from the database and rerun delorean::

    $ sudo sqlite3 commits.sqlite
    sqlite> delete from commits where status == "FAILED";


Output and log files
--------------------

The output of Delorean is generated in the ``<datadir>/repos`` directory. It consists
of the finished ``.rpm`` files for download, located in ``/repos/current``, and reports
of the failures in ``/repos/status_report.html``, and a report of all builds in
``/repos/report.html``.
