FROM fedora:21

RUN yum clean all && \
  yum update -y --nogpg && \
  yum install -y --nogpg rpm-build git python-setuptools yum-utils python2-devel intltool make python-pip gcc yum-plugin-priorities && \
  yum clean all


# Only added to speed up image builds
# TODO(derekh): Make this optional
RUN yum install -y --nogpg python-sqlalchemy python-webob python-eventlet ghostscript graphviz python-sphinx && \
  yum clean all
