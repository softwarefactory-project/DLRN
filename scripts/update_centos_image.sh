#!/bin/bash -xe

yum clean all
yum update -y --nogpg
rpm -ivh http://dl.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-5.noarch.rpm
yum install -y --nogpg rpm-build git python-setuptools yum-utils python2-devel intltool make python-pip gcc yum-plugin-priorities
# temp deps
yum install -y --nogpg python-sqlalchemy python-webob python-eventlet ghostscript graphviz python-sphinx 
