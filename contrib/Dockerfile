FROM centos:7
LABEL maintainer="jpena@redhat.com"

RUN yum -y install epel-release && yum -y update && yum -y install git createrepo mock gcc redhat-rpm-config rpmdevtools httpd libffi-devel openssl-devel yum-utils python-pip && yum clean all && rm -rf /var/cache/yum
RUN git clone https://github.com/softwarefactory-project/DLRN && pushd DLRN && pip install -r requirements.txt && pip install . && popd && sed -i 's/^app.run.*/app.run(debug=True, host="0.0.0.0")/' DLRN/scripts/api.py

COPY import.py /
COPY run.sh /
RUN chmod 755 /run.sh

EXPOSE 5000

CMD ["/run.sh"]
