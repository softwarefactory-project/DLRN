#!/bin/bash -xe

yum clean all
yum update -y --nogpg
yum install -y --nogpg rpm-build git python-setuptools yum-utils python2-devel intltool make python-pip gcc yum-plugin-priorities
# temp deps
yum install -y --nogpg python-sqlalchemy python-webob python-eventlet ghostscript graphviz python-sphinx 
