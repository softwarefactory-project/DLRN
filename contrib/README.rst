==================
DLRN API container
==================

This directory contains a set of files used to build a ready to use DLRN API
container image.

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

The container image exposes the DLRN API on port 5000, using HTTP. It support
the following environment variables:

- ``DLRNAPI_USE_SAMPLE_DATA``: if set to any value, the container will
  pre-create some basic data (commits, CI votes and a user ``foo``, with
  password ``bar``). This can be useful for tests.

An example command-line using podman, where we use the sample data:

.. code-block:: shell-session

    # podman run -p 5000:5000 -e DLRNAPI_USE_SAMPLE_DATA=yes dlrnapi:latest

For Docker, with no sample data:

.. code-block:: shell-session

    # docker run -p 5000:5000 dlrnapi:latest
