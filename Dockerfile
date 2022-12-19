FROM quay.io/centos/centos:stream9

COPY --from=quay.io/eerez/python-builder:stream9-3.11.0-sqlite /python /python-installation
RUN dnf update -y && dnf install -y make gcc && cd /python-installation && make install

COPY . app/
WORKDIR app/

RUN python3 -m pip install --upgrade pip  && \
    python3 -m pip install -I --no-cache-dir -r requirements.txt vcversioner && \
    dnf clean all && rm -rf /python-installation

CMD ["python3", "-m", "bug_master"]
