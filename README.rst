========
delorean
========

Delorean builds and maintains yum repositories following openstacks uptream repositories.

Setup
-----

.. code-block:: bash

    $ yum install git createrepo python-virtualenv git-hg mock
    $ # Add the user you intend to run as to the mock group and login again
    $ git clone https://github.com/openstack-packages/delorean.git

If you want to serv the built packages and the status reports:

.. code-block:: bash

    $ systemctl start httpd

Running
-------

.. code-block:: bash

    $ cd delorean
    $ virtualenv ../delorean-venv
    $ . ../delorean-venv/bin/activate
    $ pip install -r requirements.txt
    $ python setup.py develop
    $ # edit projects.ini if needed
    $ delorean --config-file projects.ini


Dependencies
------------
Some of the projects require others to build. As a result, the first build of
some projects may fail. The simplest solution at the moment is to allow this
to happen, delete the record of the failed builds from the database, then
rerun delorean.

.. code-block:: bash

    $ sudo sqlite3 commits.sqlite
    SQLite version 3.8.5 2014-06-04 14:06:34
    Enter ".help" for usage hints.
    sqlite> delete from commits where status == "FAILED";


Other requirements
------------------
If the git clone operation fails for a package, Delorean will try to remove
the source directory using sudo. Please make sure the user running Delorean
can run "rm -rf /path/to/delorean/data/*" without being asked for a password,
otherwise Delorean will fail to process new commits.
