====
DLRN
====

DLRN builds and maintains yum repositories following OpenStack
uptream commit streams.

Documentation is available at
http://dlrn.readthedocs.org/en/latest/

Setup
-----

.. code-block:: shell-session

    # yum install git createrepo python-virtualenv mock gcc redhat-rpm-config rpmdevtools httpd

Add the user you intend to run as to the mock group and login again.

.. code-block:: shell-session

    $ git clone https://github.com/openstack-packages/DLRN.git

If you want to serve the built packages and the status reports:

.. code-block:: shell-session

    # systemctl start httpd

Preparing
---------

.. code-block:: shell-session

    $ cd DLRN
    $ virtualenv ../dlrn-venv
    $ . ../dlrn-venv/bin/activate
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

    $ dlrn --config-file projects.ini --order

When using this special option, a special variable ``repo_bootstrap``
is defined in the specs, with a value of 1. You can use this variable if
needed, to break dependency loops between packages. For example:

.. code-block:: spec

    %if 0%{?repo_bootstrap} == 0
    BuildRequires: package-with-circular-dependency
    %endif

Running
-------

Once all the packages have been built once, you can get back to build
the packages in the order of the timestamps of the commits.

.. code-block:: shell-session

    $ dlrn --config-file projects.ini

Troubleshooting
---------------

If you interrupt dlrn during mock build you might get an error

.. code-block:: shell-session

    OSError: [Errno 16] Device or resource busy: '/var/lib/mock/dlrn-fedora-x86_64/root/var/cache/yum'

Solution is to clear left-over bind mount as root:

.. code-block:: shell-session

    # umount /var/lib/mock/dlrn-fedora-x86_64/root/var/cache/yum

Other requirements
------------------

If the git clone operation fails for a package, DLRN will try to remove
the source directory using sudo. Please make sure the user running DLRN
can run ``rm -rf /path/to/dlrn/data/*`` without being asked for a password,
otherwise DLRN will fail to process new commits.
