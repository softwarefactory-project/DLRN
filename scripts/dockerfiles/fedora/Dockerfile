FROM fedora:22

RUN dnf clean all && \
  dnf update -y --nogpg && \
  dnf install -y --nogpg rpm-build git python-setuptools python2-devel intltool make python-pip gcc 'dnf-command(builddep)' && \
  dnf clean all


# Only added to speed up image builds
# TODO(derekh): Make this optional
RUN dnf install -y --nogpg python-sqlalchemy python-webob python-eventlet ghostscript graphviz python-sphinx && \
  dnf clean all
