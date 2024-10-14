FROM registry.access.redhat.com/ubi9/python-311:latest

ARG release=main
ARG version=latest

LABEL com.redhat.component bug-master-bot
LABEL description "Slack bot for handling PROW failures on slack CI channels"
LABEL summary "Slack bot for handling PROW failures on slack CI channels"
LABEL io.k8s.description "Slack bot for handling PROW failures on slack CI channels"
LABEL distribution-scope public
LABEL name bug-master-bot
LABEL release ${release}
LABEL version ${version}
LABEL url https://github.com/openshift-assisted/bug-master-bot
LABEL vendor "Red Hat, Inc."
LABEL maintainer "Red Hat"

# License
USER 0
RUN mkdir /licenses/ && chown 1001:0 /licenses/
USER 1001
COPY LICENSE /licenses/

COPY --chown=1001:0 . .

RUN pip install --upgrade pip pip-licenses && make install && pip-licenses -l -f json --output-file /licenses/licenses.json

COPY . app/
WORKDIR app/

CMD ["bug-master"]
