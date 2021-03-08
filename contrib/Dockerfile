FROM centos:8
LABEL maintainer="jpena@redhat.com"

RUN \
    yum -y install epel-release && \
    yum -y update && \
    yum -y install git createrepo mock redhat-rpm-config rpmdevtools yum-utils python3-pip && \
    yum clean all -y && \
    rm -rf /var/cache/yum && \
    git clone https://github.com/softwarefactory-project/DLRN && \
    pushd DLRN && \
    sed -i 's#^REPO_PATH.*#REPO_PATH = "/data/repos"#' dlrn/api/config.py &&  \
    sed -i 's/^app.run.*/app.run(debug=True, host="0.0.0.0")/' scripts/api.py && \
    pip3 install --upgrade pip && \
    pip3 install -r requirements.txt && \
    pip3 install . && \
    popd && \
    mkdir /data && \
    chgrp -R 0 /data && \
    chmod -R g=u /data && \
    chmod -R g=u /DLRN

COPY import.py /
COPY run.sh /

RUN chmod 755 /run.sh

VOLUME ["/data"]
EXPOSE 5000

CMD ["/run.sh"]
