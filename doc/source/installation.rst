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
    baseurl=http://trunk.rdoproject.org/centos7/
    distro=rpm-master
    source=master
    target=centos
    smtpserver=
    reponame=delorean
    templatedir=./dlrn/templates
    maxretries=3
    pkginfo_driver=dlrn.drivers.rdoinfo.RdoInfoDriver
    tags=
    rsyncdest=
    rsyncport=22
    workers=1
    gerrit_topic=rdo-FTBFS
    database_connection=sqlite:///commits.sqlite
    fallback_to_master=1

* ``datadir`` is the directory where the packages and repositories will be
  created.

* ``scriptsdir`` is the directory where scripts utilized during the build and
  test process are located.

* ``baseurl`` is the URL to the data-directory, as hosted by your web-server.
  Unless you are installing DLRN for local use only, this must be a publicly
  accessible URL.

* ``distro`` is the branch to use for building the packages.

* ``source`` is the branch to use from the upstream repository.

* ``target`` is the distribution to use for building the packages (``centos``
  or ``fedora``).

* ``smtpserver`` is the address of the mail server for sending out notification
  emails.  If this is empty no emails will be sent out. If you are running DLRN
  locally, then do not set an smtpserver.

* ``reponame`` name of the directory that contains the generated repository.

* ``templatedir`` path to the directory that contains the report templates and
  stylesheets.

* ``maxretries`` is the maximum number of retries on known errors before
  marking the build as failed. If a build fails, DLRN will check the log files
  for known, transient errors such as network issues. If the build fails for
  that reason more than maxretries times, it will be marked as failed.

* ``pkginfo_driver`` is the driver to use for generating the list of packages
  that will be built.

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

* ``pkginfo_driver`` defines the driver to be used to manage the distgit
  repositories. There are currently two drivers:

  * ``dlrn.drivers.rdoinfo.RdoInfoDriver``, which uses information provided by
    `rdoinfo <https://github.com/redhat-openstack/rdoinfo>`_ to determine the
    distgit repo location and information.
  * ``dlrn.drivers.gitrepo.GitRepoDriver``, which uses a single Git repository
    with per-distgit directories, following the same schema used by the
    `RPM Packaging for OpenStack <https://github.com/openstack/rpm-packaging>`_
    project. This driver requires setting some optional configuration options
    in the ``[gitrepo_driver]`` section

The optional ``[gitrepo_driver]`` section has the following configuration
options:

.. code-block:: ini

    [gitrepo_driver]
    repo=http://github.com/openstack/rpm-packaging
    directory=/openstack
    skip=openstack-macros,keystoneauth1
    use_version_from_spec=0

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

Configuring for gerrit
++++++++++++++++++++++

You first need ``git-review`` installed. You can use a package or install
it using pip.

Then the username for the user creating the gerrit reviews when a
build will fail needs to be configured like this::

  $ git config --global --add gitreview.username "myaccount"

and authorized to connect to gerrit without password.

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
with the required string, using `the SQLAlchemy syntax
 <http://docs.sqlalchemy.org/en/latest/core/engines.html#database-urls>`_.

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
steps detailed in the `MariaDB documentation
 <https://mariadb.com/kb/en/mariadb/secure-connections-overview/>`_ to enable TLS
support on your server. Generate the client key and certificates, and then set up
your database connection string as follows:

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
