FROM ubuntu:14.04

RUN apt-get update -y
RUN apt-get dist-upgrade -y
RUN apt-get install -y build-essential git python-setuptools python-dev intltool python-pip devscripts equivs gdebi-core

# Only added to speed up image builds
RUN apt-get install -y python-sqlalchemy python-webob python-eventlet ghostscript graphviz python-sphinx
