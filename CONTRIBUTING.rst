============
Contributing
============

Setting up a development environment
------------------------------------

Installing prerequisites::

    $ sudo yum install docker-io git createrepo python-virtualenv git-hg
    $ sudo systemctl start httpd
    $ sudo systemctl start docker

Add the user you intend to run as to the docker group::

    $ sudo usermod -a -G docker $USER
    $ newgrp docker
    $ newgrp $USER

Checkout the Source code and install a virtualenv::

    $ git clone https://github.com/openstack-packages/delorean.git
    $ git clone https://github.com/redhat-openstack/rdoinfo
    $ cd delorean/delorean
    $ ln -sv ../../rdoinfo/rdoinfo/__init__.py rdoinfo.py
    $ cd ..
    $ virtualenv .venv
    $ source .venv/activate
    $ pip install -r requirements.txt
    $ pip install -r test-requirements.txt
    $ python setup.py develop

Submitting pull requests
------------------------

Pull requests submitted through GitHub will be ignored.  They should be sent
to GerritHub instead, using git-review.  Once submitted, they will show up
here:

   https://review.gerrithub.io/#/q/status:open+and+project:openstack-packages/delorean

Generating the documentation
----------------------------

The documentation is generated with `Sphinx <http://sphinx-doc.org/>`_. To generate
the documentation, go to the documentation directory and run the make file::

     $ cd delorean/doc/source
     $ make html

The output will be in delorean/doc/build/html
