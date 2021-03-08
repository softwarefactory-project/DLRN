==================
DLRN API container
==================

This directory contains a set of files used to build a ready to use DLRN API
container image, and the YAML file needed to publish it in the `CentOS
Container Registry <https://registry.centos.org>`_.

Creating the image
------------------

You can build the image using Buildah:

.. code-block:: shell-session

    # buildah build-using-dockerfile -t dlrnapi:latest -f Dockerfile .

and also Docker:

.. code-block:: shell-session

    # docker build -t dlrnapi:latest -f Dockerfile .

Running
-------

The container image exposes the DLRN API on port 5000, using HTTP. It supports
the following environment variables:

- ``DLRNAPI_USE_SAMPLE_DATA``: if set to any value, the container will
  pre-create some basic data (commits, CI votes and a user ``foo``, with
  password ``bar``). This can be useful for tests.

- ``DLRNAPI_DBPATH``: if set to any value, the container will use this
  connection string to connect to a database supported by SQLAlchemy. If not set,
  it will default to a local SQLite3 database.

An example command-line using podman, where we use the sample data:

.. code-block:: shell-session

    # podman run -p 5000:5000 -e DLRNAPI_USE_SAMPLE_DATA=yes dlrnapi:latest

For Docker, with no sample data:

.. code-block:: shell-session

    # docker run -p 5000:5000 dlrnapi:latest

Data is stored in that /data directory inside the container, so you can use
a volume to persist it across multiple executions:

.. code-block:: shell-session

    # podman run -p 5000:5000 --volume dlrn-data:/data dlrnapi:latest
