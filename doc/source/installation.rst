============
Installation
============

Installing prerequisites:

.. code-block:: bash

    $ sudo yum install git createrepo python-virtualenv mock gcc redhat-rpm-config rpmdevtools httpd \
      libffi-devel openssl-devel

Add the user you intend to run as to the mock group:

.. code-block:: bash

    $ sudo usermod -a -G mock $USER
    $ newgrp mock
    $ newgrp $USER

If you want to serve the built packages and the status reports:

.. code-block:: bash

    $ sudo systemctl start httpd

Install DLRN:

.. code-block:: bash

    $ pip install dlrn

Or, if you have virtualenv installed:

.. code-block:: bash

    $ virtualenv dlrn-venv
    $ source dlrn-venv/bin/activate
    $ pip install dlrn

The httpd module is not strictly required, DLRN does not use it. However, it will output
it's results in a way that is suitable for a web-server to serve. This means you can easily set up
a web-server to serve the finished ``.rpm`` and ``.log`` files.


Configuration
-------------

Configuration is done in an INI-file. An example file called ``projects.ini`` is included.
The configuration file looks like this:

.. code-block:: ini

    [DEFAULT]
    datadir=./data
    scriptsdir=./scripts
    configdir=
    baseurl=http://trunk.rdoproject.org/centos7/
    distro=rpm-master
    source=master
    target=centos
    project_name=RDO
    smtpserver=
    reponame=delorean
    templatedir=./dlrn/templates
    maxretries=3
    pkginfo_driver=dlrn.drivers.rdoinfo.RdoInfoDriver
    build_driver=dlrn.drivers.mockdriver.MockBuildDriver
    tags=
    rsyncdest=
    rsyncport=22
    workers=1
    gerrit_topic=rdo-FTBFS
    database_connection=sqlite:///commits.sqlite
    fallback_to_master=1
    nonfallback_branches=^master$,^rpm-master$,^rhos-
    coprid=account/repo
    release_numbering=0.date.hash
    custom_preprocess=
    include_srpm_in_repo=true
    keep_changelog=false

* ``datadir`` is the directory where the packages and repositories will be
  created. If not set, it will default to ``./data`` on the parent directory
  of where DLRN is installed.

* ``scriptsdir`` is the directory where scripts utilized during the build and
  test process are located. If not set, it will default to ``./scripts`` on the
  parent directory of where DLRN is installed.

* ``configdir`` is the directory where additional configuration files used by
  the build process are located, such as base mock configurations. If not set,
  it defaults to the value of ``scriptsdir``.

* ``baseurl`` is the URL to the data-directory, as hosted by your web-server.
  Unless you are installing DLRN for local use only, this must be a publicly
  accessible URL.

* ``distro`` is the branch to use for building the packages.

* ``source`` is the branch to use from the upstream repository.

* ``target`` is the distribution to use for building the packages (``centos``
  or ``fedora``).

* ``project_name`` name of the project for which DLRN is building RPMs.
  This name is used to render various templates (emails, web pages).

* ``smtpserver`` is the address of the mail server for sending out notification
  emails.  If this is empty no emails will be sent out. If you are running DLRN
  locally, then do not set an smtpserver.

* ``reponame`` name of the directory that contains the generated repository.

* ``templatedir`` path to the directory that contains the report templates and
  stylesheets. If not set, it will default to ``./templates`` under the directory
  where DLRN is installed.

* ``maxretries`` is the maximum number of retries on known errors before
  marking the build as failed. If a build fails, DLRN will check the log files
  for known, transient errors such as network issues. If the build fails for
  that reason more than maxretries times, it will be marked as failed.

* ``gerrit`` if set to anything, instructs dlrn to create a gerrit review when
  a build fails. See next section for details on how to configure gerrit to
  work.

* If ``gerrit`` is set, then ``gerrit_topic`` will define the Gerrit topic to
  use when a review is opened.

* ``tags`` is used to filter information received to decide what packages are
  built. Should be set to a release name (e.g. mitaka) to instruct the builder
  to only show packages with that release tag.

* ``rsyncdest`` if set, specifies a destination path where the hashed
  repository directories created by DLRN will be synchronized using ``rsync``,
  after each commit build.  An example would be
  ``root@backupserver.example.com:/backupdir``.  Make sure the user running
  DLRN has access to the destination server using passswordless SSH.

* ``rsyncport`` is the SSH port to be used when synchronizing the hashed
  repository. If ``rsyncdest`` is not defined, this option will be ignored.

* ``workers`` is the number of parallel build processes to launch. When using
  multiple workers, the mock build part will be handled by a pool of processes,
  while the repo creation and synchronization will still be sequential.

* The ``database_connection`` string defines a database connection string. By
  default, a local SQLite3 database is used, but it is also possible to set up
  an external database.

* ``fallback_to_master`` defines the fallback behavior when cloning Git
  repositories.

  * With the default value of 1, DLRN will fall back to the ``master`` branch
    for source repositories if the configured branch cannot be found, and
    ``rpm-master`` for distgit repositories.
  * If the value is 0, there will be no fallback, so if the configured branch
    does not exist an error message will be displayed, and the project will be
    ignored when deciding which packages need to be built.

* ``nonfallback_branches`` defines a list of regular expressions of branches for
  source and distgit repositories that should never fall back to other branches,
  even if not present in the repository. This is used when we want to avoid certain
  type of fallback that could cause issues in our environment.

  The default value is ``^master$,^rpm-master$``, which means that branches named
  ``master`` or ``rpm-master`` will never try to fall back.

* ``pkginfo_driver`` defines the driver to be used to manage the distgit
  repositories. Following drivers are available:

  * ``dlrn.drivers.rdoinfo.RdoInfoDriver``, which uses information provided by
    `rdoinfo <https://github.com/redhat-openstack/rdoinfo>`_ to determine the
    distgit repo location and information.
  * ``dlrn.drivers.downstream.DownstreamInfoDriver``, which uses information
    provided by a ``distroinfo`` repo such as
    `rdoinfo <https://github.com/redhat-openstack/rdoinfo>`_
    while reusing ``distro_hash`` and ``commit_hash`` from a remote
    ``versions.csv`` file specified by ``versions_url`` config option in the
    ``[downstream_driver]`` section. It will also use a separate distgit to
    build the driver. The distgit URL will be defined by the ``downstream_distgit_base``
    URL + the package name, and the distgit branch to use will be defined by
    the ``downstream_distro_branch`` variable.
  * ``dlrn.drivers.gitrepo.GitRepoDriver``, which uses a single Git repository
    with per-distgit directories, following the same schema used by the
    `RPM Packaging for OpenStack <https://github.com/openstack/rpm-packaging>`_
    project. This driver requires setting some optional configuration options
    in the ``[gitrepo_driver]`` section.
  * ``dlrn.drivers.local.LocalDriver``, which uses a current directory to
    discover a specfile. The current directory must be a git repository. The
    specfile is used as it is to build the rpm(s). This driver does not require
    specific configuration options.

* ``build_driver`` defines the driver used to build the packages. Source RPMs
  are always created using Mock, but the actual RPM build process can use the
  following drivers:

  * ``dlrn.drivers.mockdriver.MockBuildDriver``, which uses Mock to build the
    package. There are some optional configuration options in the
    ``[mockbuild_driver]`` section.
  * ``dlrn.drivers.kojidriver.KojiBuildDriver``, which uses `koji <https://fedoraproject.org/wiki/Koji>`_
    to build the package. There are some mandatory configuration options in the
    ``[kojibuild_driver]`` section. To use this driver, you need to make sure
    the ``koji`` command (or any alternative if you use a different binary)
    is installed on the system.
  * ``dlrn.drivers.coprdriver.CoprBuildDriver``, which uses `copr <https://fedoraproject.org/wiki/Category:Copr>`_
    to build the package. The mandatory configuration ``coprid`` option in the
    ``[coprbuild_driver]`` section must be set to use this driver. You need to
    make sure the ``copr-cli`` command is installed on the system. Configure
    only one target architecture per COPR builder else it would confuse DLRN.

* ``release_numbering`` defines the algorithm used by DLRN to assign release
  numbers to packages. The release number is created from the current date and
  the source repository git hash, and can use two algorithms:

  * ``0.date.hash`` if the old method is used: 0.<date>.<hash>
  * ``0.1.date.hash`` if the new method is used: 0.1.<date>.<hash>. This new
    method provides better compatibility with the Fedora packaging guidelines.

* ``custom_preprocess``, if set, defines a comma-separated list of custom programs
  or scripts to be called as part of the pre-process step. The custom programs will
  be executed sequentially.

  After the distgit is cloned, and before the source RPM is built, the ``pkginfo``
  drivers run a pre-process step where some actions are taken on the repository,
  such as Jinja2 template processing. In addition to this per-driver step, a
  custom pre-process step can be specified.
  The external program(s) will be executed with certain environment variables set:

  * ``DLRN_PACKAGE_NAME``: name of the package being built.
  * ``DLRN_DISTGIT``: path to the distgit in the local file system.
  * ``DLRN_SOURCEDIR``: path to the source git in the local file system.
  * ``DLRN_SOURCE_COMMIT``: commit hash of the source repository being built.
  * ``DLRN_USER``: name of the user running DLRN.
  * ``DLRN_UPSTREAM_DISTGIT``: for the ``downstream`` driver, path to the
    upstream distgit in the local file system.
  * ``DLRN_DISTROINFO_REPO``: for the ``rdoinfo`` and ``downstream`` drivers,
    path to the local or remote distroinfo repository used by the instance.

  Do not assume any other environment variable (such as PATH), since it may not
  be defined.

* ``include_srpm_in_repo``, if set to true (default), includes source RPMs in the
  repositories generated by DLRN. If set to false, DLRN will exclude source RPMs
  from the repositories.

* ``keep_changelog``, if set to true, will not clean the %changelog section from
  spec files when building the source RPM. When set to the default value of
  ``false``, DLRN will remove all changelog content from specs.

The optional ``[gitrepo_driver]`` section has the following configuration
options:

.. code-block:: ini

    [gitrepo_driver]
    repo=http://github.com/openstack/rpm-packaging
    directory=/openstack
    skip=openstack-macros,keystoneauth1
    use_version_from_spec=0
    keep_tarball=0

* ``repo`` is the single Git repository where all distgits are located.
* ``directory`` is a directory inside the repo. DLRN will expect each
  directory inside it to include the spec file for a single project, using
  a Jinja2 template like in the RPM Packaging for OpenStack project.
* ``skip`` is a comma-separated list of directories to skip from ``directory``
  when creating the list of packages to build. This can be of use when the
  Git repo contains one or more directories without a spec file in it, or
  the package should not be built for any other reason.
* ``use_version_from_spec`` If set to 1 (or true), the driver will parse the
  template spec file and set the source branch to the Version: tag in the spec.
* ``keep_tarball`` If set to 1 (or true), and the spec template detects the
  package version automatically using a tarball (see [1]_), DLRN will not
  replace the Source0 file with a tarball generated from the Git repo, but it
  will use the same tarball used to detect the package version. This defeats
  the purpose of following the commits from Git, but it is useful in certain
  scenarios, such as CI testing, when the tarball or its tags may not be in
  sync with the Git contents.

The optional ``[rdoinfo_driver]`` section has the following configuration
options:

.. code-block:: ini

    [rdoinfo_driver]
    repo=http://github.com/org/rdoinfo-fork
    info_files=file.yml
    cache_dir=~/.distroinfo/cache

* ``repo`` defines the rdoinfo repository to use. This setting
  must be set if a fork of the rdoinfo repository must be used.
* ``info_files`` selects an info file (or a list of info files) to get package
  information from (within the distroinfo repo selected with ``repo``). It
  defaults to ``rdo.yml``.
* ``cache_dir`` defines the directory uses for caching to avoid downloading
  the same repo multiple times. By default, it uses None.
  A different base directory for the cache can be set for both ``[rdoinfo_driver]``
  and ``[downstream_driver]``

The optional ``[downstream_driver]`` section has the following configuration
options:

.. code-block:: ini

    [downstream_driver]
    repo=http://github.com/org/fooinfo
    info_files=foo.yml
    versions_url=https://trunk.rdoproject.org/centos7-master/current/versions.csv
    downstream_distro_branch=foo-rocky
    downstream_tag=foo-
    downstream_distgit_tag=foo-distgit
    use_upstream_spec=False
    downstream_spec_replace_list=^foo/bar,string1/string2
    cache_dir=~/.distroinfo/cache

* ``repo`` selects a distroinfo repository to get package information from.
* ``info_files`` selects an info file (or a list of info files) to get package
  information from (within the distroinfo repo selected with ``repo``)
* ``versions_url`` must point to a ``versions.csv`` file generated by
  DLRN instance. ``distro_hash`` and ``commit_hash`` will be reused from
  supplied ``versions.csv`` and only packages present in the file are
  processed.
* ``downstream_distro_branch`` defines which branch to use when cloning the
  downstream distgit, since it may be different from the upstream distgit branch.
* ``downstream_tag`` if set, it will filter the ``packages`` section of packaging
  metadata (from ``repo``/``info_files``) to only contain packages with
  the ``downstream_tag`` tag. This tag will be filtered in addition to the one
  set in the ``DEFAULT/tags`` section.
* ``downstream_distgit_key`` is the key used to find the downstream distgit in
  the ``packages`` section of packaging metadata (from ``repo``/``info_files``).
* ``use_upstream_spec`` defines if the upstream distgit contents (spec file and
  additional files) should be copied over the downstream distgit after cloning.
* ``downstream_spec_replace_list``, when ``use_upstream_spec`` is set to True,
  will perform some sed-like edits in the spec file after copying it from the
  upstream to the downstream distgit. This is specially useful when the
  downstream DLRN instance has special requirements, such as building without
  documentation. in that case, a regular expresion like the following could be
  used:

.. code-block:: ini
    downstream_spec_replace_list=^%global with_doc.+/%global with_doc 0

  Multiple regular expressions can be used, separated by commas.

* ``cache_dir`` defines the directory uses for caching to avoid downloading
  the same repo multiple times. By default, it uses None.
  A different base directory for the cache can be set for both ``[rdoinfo_driver]``
  and ``[downstream_driver]``

The optional ``[mockbuild_driver]`` section has the following configuration
options:

.. code-block:: ini

    [mockbuild_driver]
    install_after_build=1

* The ``install_after_build`` boolean option defines whether mock should
  try to install the newly created package in the same buildroot or not.
  If not specified, the default is ``True``.

The optional ``[kojibuild_driver]`` section is only taken into account if the
build_driver option is set to ``dlrn.drivers.kojidriver.KojiBuildDriver``. The
following configuration options are included:

.. code-block:: ini

    [kojibuild_driver]
    koji_exe=koji
    krb_principal=user@EXAMPLE.COM
    krb_keytab=/home/user/user.keytab
    scratch_build=True
    build_target=koji-target-build
    arch=aarch64
    use_rhpkg=False
    fetch_mock_config=False
    mock_base_packages=basesystem rpm-build

* ``koji_exe`` defines the executable to use. Some Koji instances create their
  own client packages to add their default configuration, such as
  `CBS <https://wiki.centos.org/HowTos/CommunityBuildSystem>`_ or Brew.
  If not specified, it will default to ``koji``.
* ``krb_principal`` defines the Kerberos principal to use for the Koji builds.
  If not specified, DLRN will assume that authentication is performed using SSL
  certificates.
* ``krb_keytab`` is the full path to a Kerberos keytab file, which contains the
  Kerberos credentials for the principal defined in the ``krb_principal``
  option.
* ``scratch_build`` defines if a scratch build should be used. By default, it
  is set to ``True``.
* ``build_target`` defines the build target to use. This defines the buildroot
  and base repositories to be used for the build.
* ``arch`` allows to override default architecture (x86_64) in some cases (e.g
  retrieving mock configuration from Koji instance).
* ``use_rhpkg`` allows us to use ``rhpkg`` as the build tool in combination with
  ``koji_exe``. That involves some changes in the workflow:
  * Instead of using ``koji_exe`` to trigger the build, DLRN will generate the
    source RPM, and upload it to the distgit path using ``rhpkg import``.
  * DLRN will run ``rhpkg build`` to actually trigger the build.

  Note that ``rhpkg`` requires a valid Kerberos ticket, so the ``krb_principal``
  and ``krb_keytab`` options must be set.

  Also note that setting ``rhpkg`` only makes sense when using ``dlrn.drivers.downstream.DownstreamInfoDriver``
  as the pkginfo driver.
* ``fetch_mock_config``, if set to ``true``, will instruct DLRN to download the
  mock configuration for the build target from Koji, and use it when building
  the source RPM. If set to ``false``, DLRN will use its internally defined mock
  configuration, based on the ``DEFAULT/target`` configuration option.
* ``mock_base_packages``, if  ``fetch_mock_config`` is set to ``true``, will
  define the set of base packages that will be installed in the mock configuration
  when creating the source RPM. This list of packages will override the one
  fetched in the mock configuration, if set. If not set, no overriding will
  be done.

The optional ``[coprbuild_driver]`` section has the following configuration
options:

.. code-block:: ini

    [coprbuild_driver]
    coprid=account/repo

* The ``coprid`` option defines Copr id to use to compile the packages.

Configuring for gerrit
++++++++++++++++++++++

You first need ``git-review`` installed. You can use a package or install
it using pip.

Then the username for the user creating the gerrit reviews when a
build will fail needs to be configured like this:

  $ git config --global gitreview.username dlrnbot
  $ git config --global user.email dlrn@dlrn.domain

and authorized to connect to Gerrit without password. Make sure
the public SSH key of the user that run DLRN is defined in
the Gerrit account linked to the DLRN user email.

Configuring your httpd
----------------------

The output generated by DLRN is a file structure suitable for serving with a web-server.
You can either add a section in the server configuration where you map a URL to the
data directories, or just make a symbolic link:

.. code-block:: bash

    $ cd /var/www/html
    $ sudo ln -s <datadir>/repos .


Database support
----------------

DLRN supports different database engines through SQLAlchemy. SQLite3 and MariaDB have
been tested so far. You can set the ``database_connection`` parameter in projects.ini
with the required string, using `the SQLAlchemy syntax`_.

.. _the SQLAlchemy syntax: http://docs.sqlalchemy.org/en/latest/core/engines.html#database-urls

For MariaDB, use a mysql+pymysql driver, with the following string:

.. code-block:: ini

    database_connection=mysql+pymysql://user:password@serverIP/dlrn

That requires you to pre-create the ``dlrn``database.

If your MariaDB database is placed on a publicly accessible server, you will want to
secure it as a first step:

.. code-block:: bash

    $ sudo mysql_secure_installation

You can use the following commands to create the database and grant the required permissions:

.. code-block:: mysql

    use mysql
    create database dlrn;
    grant all on dlrn.* to 'user'@'%' identified by 'password';
    flush privileges;

You may also want to enable TLS support in your connections. In this case, follow the
steps detailed in the `MariaDB documentation`_ to enable TLS
support on your server. Generate the client key and certificates, and then set up
your database connection string as follows:

.. _MariaDB documentation: https://mariadb.com/kb/en/mariadb/secure-connections-overview/

.. code-block:: ini

    database_connection=mysql+pymysql://user:password@serverIP/dlrn?ssl_cert=/dir/client-cert.pem&ssl_key=/dir/client-key.pem

You can also force the MySQL user to connect using TLS if you create it as follows:

.. code-block:: mysql

    use mysql
    create database dlrn;
    grant all on dlrn.* to 'user'@'%' identified by 'password' REQUIRE SSL;
    flush privileges;

Database migration
++++++++++++++++++

During DLRN upgrades, you may need to upgrade the database schemas,
in order to keep your old history.
To migrate database to the latest revision, you need the alembic command-line
and to run the ``alembic upgrade head`` command.

.. code-block:: bash

    $ sudo yum install -y python-alembic
    $ alembic upgrade head

If the database doesn't exist, ``alembic upgrade head`` will create it from scratch.

If you are using a MariaDB database, the initial schema will not be valid. You should
start by running DLRN a first time, so it creates the basic schema, then run the
following command to stamp the database to the first version of the schema that
supported MariaDB:

.. code-block:: bash

    $ alembic stamp head

After that initial command, you will be able to run future migrations.

Adding a custom mock base configuration
+++++++++++++++++++++++++++++++++++++++

The source RPM build operations, and the binary RPM build by default, are performed
using ``mock``. Mock uses a configuration file, and DLRN provides sample files for
CentOS and Fedora in the ``scripts/`` directory.

You may want to use a different base mock configuration, if you need to specify a
different base package set or an alternative yum repository. The procedure to do so
is the following:

* Edit the ``configdir`` variable in your projects.ini file, and make it point to
  a configuration directory.

* In that new directory, create the configuration file. It should be named
  ``<target>.cfg``, where ``<target>`` is the value of the target option in
  projects.ini.

* For the mock configuration file syntax, refer to the `mock documentation`_.

.. _mock documentation: https://github.com/rpm-software-management/mock/wiki#generate-custom-config-file

References
==========

 .. [1] Version handling using renderspec templates
    https://github.com/openstack/renderspec/blob/master/doc/source/usage.rst#handling-the-package-version
