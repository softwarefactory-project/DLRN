========
delorean
========

Delorean builds and maintains yum repositories following openstacks uptream repositories.

* Free software: Apache license
* Documentation: http://docs.openstack.org/developer/delorean
* Source: http://git.openstack.org/cgit/stackforge/delorean
* Bugs: http://bugs.launchpad.net/delorean


Setup
-----

.. code-block:: bash

    $ yum install docker-io git createrepo python-virtualenv git-hg
    $ systemctl start httpd
    $ systemctl start docker
    $ # Add the user you intend to run as to the docker group and login again
    $ git clone https://github.com/openstack-packages/delorean.git

Running
-------

.. code-block:: bash

    $ cd delorean
    $ ./scripts/create_build_image.sh
    $ virtualenv ../delorean-venv
    $ . ../delorean-venv/bin/activate
    $ pip install -r requirements.txt
    $ python setup.py develop
    $ # edit projects.ini if needed
    $ delorean --config-file projects.ini


Dependencies
------------
In order to build Some of the projects here require others, as a result the
first build of some projects may fail, the simplest solution at the moment
is to allow this to happen, delete the record of the failed builds from the
database and rerun delorean.

.. code-block:: bash

    $ sudo sqlite3 commits.sqlite
    SQLite version 3.8.5 2014-06-04 14:06:34
    Enter ".help" for usage hints.
    sqlite> delete from commits where status == "FAILED";



