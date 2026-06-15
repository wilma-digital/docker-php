# OpenMage PHP + Node.js Container - Template
# GENERATED FILES ARE DERIVED FROM THIS TEMPLATE - edit the template, not the output.
#
# Unlike the base php image, this variant does NOT recompile PHP. It layers
# Node.js on top of the already-built wilmadigital/php:${PHP_VERSION} image,
# so PHP is compiled exactly once (in the base image) and reused here.
#
# Variables: PHP_VERSION, NODE_VERSION
# Requires:  wilmadigital/php:${PHP_VERSION} and wilmadigital/php:${PHP_VERSION}-toolbox
#            to be built/pushed first (CI: build-node needs build-base).

ARG PHP_VERSION="8.4.18"

# ---------------------------------------------------------------------------
# php + node  (runtime)
# ---------------------------------------------------------------------------
FROM wilmadigital/php:${PHP_VERSION} AS php

ARG NODE_VERSION="25"
SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

# Install Node.js via the NodeSource APT repository
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_VERSION}.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g npm@latest && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ENTRYPOINT, CMD, HEALTHCHECK, WORKDIR and EXPOSE are inherited from the base image.

# ---------------------------------------------------------------------------
# toolbox + node  (development tools)
# ---------------------------------------------------------------------------
FROM wilmadigital/php:${PHP_VERSION}-toolbox AS toolbox

ARG NODE_VERSION="25"
SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

# Install Node.js via the NodeSource APT repository
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_VERSION}.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g npm@latest && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# CMD (php -a) is inherited from the toolbox base image.
