========
Delorean
========

Delorean builds and maintains yum repositories following OpenStack
uptream commit streams.

Setup
-----

.. code-block:: shell-session

    # yum install git createrepo python-virtualenv git-remote-hg mock

Add the user you intend to run as to the mock group and login again.

.. code-block:: shell-session

    $ git clone https://github.com/openstack-packages/delorean.git

If you want to serv the built packages and the status reports:

.. code-block:: shell-session

    # systemctl start httpd

Preparing
---------

.. code-block:: shell-session

    $ cd delorean
    $ virtualenv ../delorean-venv
    $ . ../delorean-venv/bin/activate
    $ pip install -r requirements.txt
    $ python setup.py develop


Edit ``projects.ini`` if needed.

Bootstrapping
-------------

Some of the projects require others to build. As a result, use the
special option ``--order`` to build in the order computed from the
BuildRequires and Requires fields of the spec files when you bootstrap
your repository.

.. code-block:: shell-session

    $ delorean --config-file projects.ini --order

Running
-------

Once all the packages have been built once, you can get back to build
the packages in the order of the timestamps of the commits.

.. code-block:: shell-session

    $ delorean --config-file projects.ini

Troubleshooting
---------------

If you interrupt delorean during mock build you might get an error

.. code-block:: shell-session

    OSError: [Errno 16] Device or resource busy: '/var/lib/mock/delorean-fedora-x86_64/root/var/cache/yum'

Solution is to clear left-over bind mount as root:

.. code-block:: shell-session

    # umount /var/lib/mock/delorean-fedora-x86_64/root/var/cache/yum

Other requirements
------------------

If the git clone operation fails for a package, Delorean will try to remove
the source directory using sudo. Please make sure the user running Delorean
can run ``rm -rf /path/to/delorean/data/*`` without being asked for a password,
otherwise Delorean will fail to process new commits.
