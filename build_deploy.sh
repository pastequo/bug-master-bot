#!/usr/bin/env bash

set -xeuo pipefail

if command -v podman
then
    CONTAINER_CMD="podman"
else
    CONTAINER_CMD="docker"
fi
export CONTAINER_CMD
echo "Using ${CONTAINER_CMD} as container engine..."

export CONTAINER_BUILD_EXTRA_PARAMS=${CONTAINER_BUILD_EXTRA_PARAMS:-"--no-cache"}
export BUG_MASTER_IMAGE=${BUG_MASTER_IMAGE:-"quay.io/app-sre/bug-master"}

# Tag with the current commit sha
BUG_MASTER_TAG="$(git rev-parse HEAD)"
export BUG_MASTER_TAG

# Setup credentials to image registry
${CONTAINER_CMD} login -u="${QUAY_USER}" -p="${QUAY_TOKEN}" quay.io

# Build and push latest image
make build-image

BUG_MASTER_IMAGE_COMMIT_SHA="${BUG_MASTER_IMAGE}:${BUG_MASTER_TAG}"
${CONTAINER_CMD} push "${BUG_MASTER_IMAGE_COMMIT_SHA}"

# Tag with the current commit short sha
BUG_MASTER_SHORT_TAG="$(git rev-parse --short=7 HEAD)"
BUG_MASTER_IMAGE_COMMIT_SHORT_SHA="${BUG_MASTER_IMAGE}:${BUG_MASTER_SHORT_TAG}"
${CONTAINER_CMD} tag "${BUG_MASTER_IMAGE_COMMIT_SHA}" "${BUG_MASTER_IMAGE_COMMIT_SHORT_SHA}"
${CONTAINER_CMD} push "${BUG_MASTER_IMAGE_COMMIT_SHORT_SHA}"

# Tag the image as latest
BUG_MASTER_IMAGE_LATEST="${BUG_MASTER_IMAGE}:latest"
${CONTAINER_CMD} tag "${BUG_MASTER_IMAGE_COMMIT_SHA}" "${BUG_MASTER_IMAGE_LATEST}"
${CONTAINER_CMD} push "${BUG_MASTER_IMAGE_LATEST}"
