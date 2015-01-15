============
Installation
============

Installing prerequisites::

    $ sudo yum install docker-io git createrepo python-virtualenv git-hg
    $ sudo systemctl start httpd
    $ sudo systemctl start docker

Add the user you intend to run as to the docker group::

    $ sudo usermod -a -G docker $USER
    $ newgrp docker
    $ newgrp $USER

Install Delorean::

    $ pip install delorean

Or, if you have virtualenvwrapper installed::

    $ mkvirtualenv delorean
    $ pip install delorean