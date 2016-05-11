============
Contributing
============

Setting up a development environment in an OpenStack VM using cloud-init
------------------------------------------------------------------------

The following cloud-config script can be passed as a --user-data argument to
`nova boot`. This will result in a fully operational DLRN environment to
hack on.

.. code-block:: yaml
    #cloud-config
    disable_root: 0

    users:
      - default

    package_upgrade: true

    packages:
      - vim
      - git
      - policycoreutils-python-utils

    runcmd:
      - yum -y install epel-release
      - yum -y install puppet
      - git clone https://github.com/rdo-infra/puppet-dlrn /root/puppet-dlrn
      - cd /root/puppet-dlrn
      - puppet module build
      - puppet module install pkg/jpena-dlrn-*.tar.gz
      - cp /root/puppet-dlrn/examples/common.yaml /var/lib/hiera
      - puppet apply --debug /root/puppet-dlrn/examples/site.pp 2>&1 | tee /root/puppet.log

    final_message: "DLRN installed, after $UPTIME seconds."

Setting up a development environment manually
---------------------------------------------

Follow the instructions from the `Setup section <https://github.com/openstack-packages/DLRN/blob/master/README.rst#setup>`_ of `README.rst <https://github.com/openstack-packages/DLRN/blob/master/README.rst>`_ to manually setup a development environment.

Submitting pull requests
------------------------

Pull requests submitted through GitHub will be ignored.  They should be sent
to GerritHub instead, using git-review.  Once submitted, they will show up
here:

   https://review.gerrithub.io/#/q/status:open+and+project:openstack-packages/delorean

Generating the documentation
----------------------------

Please note that the `RDO Packaging Documentation
<https://www.rdoproject.org/documentation/packaging/>`_ also contains
instructions for DLRN.

The documentation is generated with `Sphinx <http://sphinx-doc.org/>`_. To generate
the documentation, go to the documentation directory and run the make file:

.. code-block:: bash

     $ cd DLRN/doc/source
     $ make html

The output will be in DLRN/doc/build/html

