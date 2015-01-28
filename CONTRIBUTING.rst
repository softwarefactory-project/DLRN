============
Contributing
============

Setting up a development environment in an OpenStack VM using cloud-init
------------------------------------------------------------------------

The following cloud-config script can be passed as a --user-data argument to
`nova boot`. This will result in a fully operational delorean environment to
hack on.

.. code-block:: yaml

    #cloud-config
    disable_root: 0
    groups:
    - docker
    package_upgrade: true
    packages: 
    - vim
    - docker-io
    - git
    - python-pip
    - git-remote-hg
    - python-virtualenv
    - httpd
    - gcc
    - createrepo
    - screen
    - python3
    - python-tox
    - git-review

    write_files:
    - content: |
        #!/bin/bash
        setenforce 0
        usermod -a -G docker root
        newgrp docker
        systemctl enable docker.service
        systemctl start docker.service
        systemctl enable httpd.service
        systemctl start httpd.service
        cd ~
        git clone https://github.com/openstack-packages/delorean
        git clone https://github.com/redhat-openstack/rdoinfo
        cd delorean/delorean
        ln -sv ~/rdoinfo/rdoinfo/__init__.py rdoinfo.py
        cd ~/delorean
        virtualenv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
        pip install -r test-requirements.txt
        python setup.py develop
        chcon -t docker_exec_t scripts/*
        scripts/create_build_image.sh
        FLOAT=`curl http://169.254.169.254/latest/meta-data/public-ipv4`
        sed -i s:209.132.178.33:$FLOAT: ~/delorean/projects.ini
        sed -i s:./data:/root/delorean/data: ~/delorean/projects.ini
        chmod +x /root
        ln -s /root/delorean/data/repos /var/www/html/
    path: /root/setup.sh
    permissions: 0744

    - content: |
        #!/bin/bash
        cd ~/delorean
        source .venv/bin/activate
        delorean --config-file ~/delorean/projects.ini --info-file ~/rdoinfo/rdo.yml
        sqlite3 ~/delorean/commits.sqlite < ~/fix-fails.sql
    path: /root/first.sh
    permissions: 0744

    - content: |
        #!/bin/bash
        LOCK='/root/delorean.lock'
        set -e

        exec 200>$LOCK
        flock -n 200 || exit 1

        source ~/delorean/.venv/bin/activate
        export PYTHONPATH=$PYTHONPATH:/root/delorean/rdoinfo
        LOGFILE=/var/log/delorean.$(date +%s).log
        
        echo `date` "Starting delorean run." >> $LOGFILE
        delorean --config-file ~/delorean/projects.ini --info-file ~/rdoinfo/rdo.yml 2>> $LOGFILE
        echo `date` "Delorean run complete." >> $LOGFILE
    path:  /root/run.sh
    permissions: 0744

    - content: |
        delete from commits where status == "FAILED";
    path:  /root/fix-fails.sql
    permissions: 0644

    runcmd:
    - mkdir /var/log/delorean
    - script -c "/root/setup.sh" /var/log/delorean/setup.log
    - script -c "/root/first.sh" /var/log/delorean/first.log
    - echo "*/5 * * * * root /root/run.sh" >> /etc/crontab

    final_message: "Delorean installed, after $UPTIME seconds."

Setting up a development environment manually
---------------------------------------------

Installing prerequisites:

.. code-block:: bash

    $ sudo yum install docker-io git createrepo python-virtualenv git-hg
    $ sudo systemctl start httpd
    $ sudo systemctl start docker

Add the user you intend to run as to the docker group:

.. code-block:: bash

    $ sudo usermod -a -G docker $USER
    $ newgrp docker
    $ newgrp $USER

Checkout the Source code and install a virtualenv:

.. code-block:: bash

    $ git clone https://github.com/openstack-packages/delorean.git
    $ git clone https://github.com/redhat-openstack/rdoinfo
    $ cd delorean/delorean
    $ ln -sv ../../rdoinfo/rdoinfo/__init__.py rdoinfo.py
    $ cd ..
    $ virtualenv .venv
    $ source .venv/bin/activate
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

Please note that the `Master Packaging Guide
<https://openstack.redhat.com/packaging/rdo-packaging.html#master-pkg-guide>`_ also contains
instructions for Delorean. If you modify the documentation, please make sure the Master Packaging
Guide is also up to date. The source code is located at
https://github.com/redhat-openstack/openstack-packaging-doc/blob/master/doc/rdo-packaging.txt .

The documentation is generated with `Sphinx <http://sphinx-doc.org/>`_. To generate
the documentation, go to the documentation directory and run the make file:

.. code-block:: bash

     $ cd delorean/doc/source
     $ make html

The output will be in delorean/doc/build/html

