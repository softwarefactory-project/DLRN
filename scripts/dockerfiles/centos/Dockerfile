FROM centos:7

RUN yum clean all
RUN yum update -y --nogpg
RUN rpm -ivh http://dl.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-5.noarch.rpm
RUN yum install -y --nogpg rpm-build git python-setuptools yum-utils python2-devel intltool make python-pip gcc yum-plugin-priorities

# Only added to speed up image builds
# TODO(derekh): Make this optional
RUN yum install -y --nogpg python-sqlalchemy python-webob python-eventlet ghostscript graphviz python-sphinx
