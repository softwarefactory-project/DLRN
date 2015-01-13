========
delorean
========

Build packages

* Free software: Apache license
* Documentation: http://docs.openstack.org/developer/delorean
* Source: http://git.openstack.org/cgit/stackforge/delorean
* Bugs: http://bugs.launchpad.net/delorean

Features
--------
Builds and maintains yum repositories following openstacks uptream repositories

Setup
-----

.. code-block:: bash

    yum install docker-io git{,-hg} createrepo python-{virtualenv,pip} httpd
    systemctl start httpd # only if you wish to serve repos/reports
    systemctl start docker
    # Add the user you intend to run as to the docker group and login again
    git clone https://github.com/openstack-packages/delorean.git
    cd delorean
    ./scripts/create_build_image.sh
    virtualenv ../delorean-venv
    . ../delorean-venv/bin/activate
    pip install -r requirements.txt
    python setup.py develop
    # edit projects.ini if needed
    cd
    git clone https://github.com/redhat-openstack/rdoinfo
    cd delorean/delorean
    ln -sv ~/rdoinfo/rdoinfo/__init__.py rdoinfo.py
    delorean --config-file projects.ini --info-file ~/rdoinfo/rdo.yml

Dependencies
------------
In order to build Some of the projects here require others, as a result the
first build of some projects may fail, the simplies solution at the moment 
is to allow this to happen, delete the record of the failed builds from the
database and rerun delorean.

.. code-block:: bash

    $ sudo sqlite3 commits.sqlite 
    SQLite version 3.8.5 2014-06-04 14:06:34
    Enter ".help" for usage hints.
    sqlite> delete from commits where status == "FAILED";


* TODO
