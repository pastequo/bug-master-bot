FROM registry.access.redhat.com/ubi9/python-311:latest

COPY --chown=1001:0 . .

RUN pip install --upgrade pip && make install

COPY . app/
WORKDIR app/

CMD ["bug-master"]
