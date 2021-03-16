===============
Troubleshooting
===============

If you interrupt dlrn during mock build you might get an error

.. code-block:: bash

    OSError: [Errno 16] Device or resource busy: '/var/lib/mock/dlrn-centos-x86_64/root/var/cache/yum'

Solution is to clear left-over bind mount as root:

.. code-block:: shell-session

    # umount /var/lib/mock/dlrn-centos-x86_64/root/var/cache/yum

Other requirements
==================

If the git clone operation fails for a package, DLRN will try to remove the
source directory using sudo. Please make sure the user running DLRN can run
``rm -rf /path/to/dlrn/data/*`` without being asked for a password, otherwise
DLRN will fail to process new commits.

API issues
==========

If you want to quickly check the API status, you can use the /api/health
endpoint. It will allow you to test API connectivity, database access and
authentication:

.. code-block:: bash

    # curl http://localhost:5000/api/health
    # curl -d test=test --user user:password http://localhost:5000/api/health
