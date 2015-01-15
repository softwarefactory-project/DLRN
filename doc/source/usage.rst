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
  --local               Use local git repo's if possible
  --head-only           Build from the most recent Git commit only.
  --package-name PACKAGE_NAME
                        Build a specific package name only.
  --dev                 Don't reset packaging git repo, force build and add
                        public master repo for dependencies (dev mode).