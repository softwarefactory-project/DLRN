FROM fedora:21

RUN yum clean all
RUN yum update -y --nogpg
RUN yum install -y --nogpg rpm-build git python-setuptools yum-utils python2-devel intltool make python-pip gcc yum-plugin-priorities


# Only added to speed up image builds
# TODO(derekh): Make this optional
RUN yum install -y --nogpg python-sqlalchemy python-webob python-eventlet ghostscript graphviz python-sphinx
