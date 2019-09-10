FROM centos:7
LABEL maintainer="jpena@redhat.com"

RUN yum -y install epel-release
RUN yum -y install git createrepo mock gcc redhat-rpm-config rpmdevtools httpd libffi-devel openssl-devel yum-utils python-pip
RUN yum -y update
RUN yum clean all
RUN rm -rf /var/cache/yum

RUN git clone https://github.com/softwarefactory-project/DLRN
RUN cd DLRN && pip install -r requirements.txt && pip install .
RUN sed -i 's/^app.run.*/app.run(debug=True, host="0.0.0.0")/' DLRN/scripts/api.py

COPY import.py /
COPY run.sh /
RUN chmod 755 /run.sh

EXPOSE 5000

CMD ["/run.sh"]
