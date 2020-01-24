FROM centos:7
LABEL maintainer="jpena@redhat.com"

RUN yum -y install epel-release && yum -y update && yum -y install git createrepo mock gcc redhat-rpm-config rpmdevtools httpd libffi-devel openssl-devel yum-utils python-pip && yum clean all -y && rm -rf /var/cache/yum
RUN git clone https://github.com/softwarefactory-project/DLRN && pushd DLRN && sed -i 's/^DB_PATH.*/DB_PATH = "sqlite:\/\/\/\/data\/commits.sqlite"/' dlrn/api/config.py && sed -i 's/^REPO_PATH.*/REPO_PATH = "\/data\/repos"/' dlrn/api/config.py &&  pip install -r requirements.txt && pip install . && popd && sed -i 's/^app.run.*/app.run(debug=True, host="0.0.0.0")/' DLRN/scripts/api.py

COPY import.py /
COPY run.sh /
RUN chmod 755 /run.sh && mkdir /data && chgrp -R 0 /data && chmod -R g=u /data

EXPOSE 5000
VOLUME /data

CMD ["/run.sh"]
