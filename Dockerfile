FROM quay.io/centos/centos:stream8
RUN dnf update -y && dnf install -y python39 && dnf clean all && python3 -m pip install --upgrade pip

COPY . app/
WORKDIR app/
RUN python3 -m pip install -I --no-cache-dir -r requirements.txt vcversioner

CMD ["python3", "-m", "bug_master"]