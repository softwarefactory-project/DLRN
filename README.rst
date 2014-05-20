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
    yum install docker-io git createrepo python-virtualenv
    systemctl start httpd
    systemctl start docker
    # Add the user you intend to run as to the docker group and login again
    git clone https://github.com/derekhiggins/delorean.git
    cd delorean
    ./scripts/create_build_image.sh
    virtualenv ../delorean-venv
    . ../delorean-venv/bin/activate
    pip install -r requirements.txt
    python setup.py develop
    # edit projects.ini if needed
    delorean --config-file projects.ini

* TODO
