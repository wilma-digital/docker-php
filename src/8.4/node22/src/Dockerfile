# OpenMage PHP + Node.js Container - Template
# GENERATED FILES ARE DERIVED FROM THIS TEMPLATE - edit the template, not the output.
#
# Unlike the base php image, this variant does NOT recompile PHP. It layers
# Node.js on top of the already-built ${BASE_IMAGE}:${PHP_VERSION}-toolbox
# image, so PHP is built exactly once (in the base image) and reused here.
#
# Node.js is only offered on the toolbox image: production fpm images do not
# need it, frontend builds in CI use the toolbox.
#
# Variables: PHP_VERSION, NODE_VERSION
# Requires:  ${BASE_IMAGE}:${PHP_VERSION}-toolbox to be built/pushed first
#            (CI: base images on Monday, Node variants on Tuesday).

ARG BASE_IMAGE="ghcr.io/wilma-digital/php"
ARG PHP_VERSION="8.4.26"

FROM ${BASE_IMAGE}:${PHP_VERSION}-toolbox AS toolbox

ARG NODE_VERSION="22"
SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

# Install Node.js via the NodeSource APT repository
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_VERSION}.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# CMD (php -a) is inherited from the toolbox base image.
