CONTAINER_CMD := $(or $(CONTAINER_CMD), $(shell command -v podman 2> /dev/null))
ifndef CONTAINER_CMD
CONTAINER_CMD := docker
endif

BUG_MASTER_IMAGE := $(or $(BUG_MASTER_IMAGE), "quay.io/edge-infrastructure/bug-master")
BUG_MASTER_TAG := $(or $(BUG_MASTER_TAG),latest)

build-image:
	$(CONTAINER_CMD) build $(CONTAINER_BUILD_EXTRA_PARAMS) -t $(BUG_MASTER_IMAGE):$(BUG_MASTER_TAG) .

install:
	pip install -r requirements.txt .

install-lint:
	pip install .[lint]

full-install: install install-lint

flake8:
	flake8 src/

format:
	black src/
	isort --profile black src

lint-manifest:
	oc process --local=true -f openshift/template.yaml --param IMAGE_TAG=foobar | oc apply --dry-run=client -f -

lint: flake8 format
	git diff --exit-code

.PHONY: install install-lint full-install format flake8 lint lint-manifest build-image
