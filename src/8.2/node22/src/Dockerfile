# OpenMage PHP Container - Template
# This template is used to generate version-specific Dockerfiles
# Variables: PHP_VERSION, BASE_IMAGE, PHP_RUNTIME_LIBS, PHP_BUILD_LIBS

FROM wilmadigital/php-base:bookworm-latest AS builder

# Build arguments
ARG PHP_VERSION="8.2.30"
ARG PHP_BUILD_REQUIREMENTS="build-essential curl dpkg-dev automake autoconf libtool file g++ gcc libc-dev make pkg-config re2c libxml2-dev libcurl4-gnutls-dev libtidy-dev libsqlite3-dev libssl-dev zlib1g-dev libpng-dev liblzf-dev libreadline6-dev libfreetype6-dev libmcrypt-dev libedit-dev libltdl-dev libxslt-dev libzip-dev libsodium-dev libonig-dev gnupg2 argon2 libargon2-0 libargon2-dev libicu-dev"
ARG PHP_BUILD_REQUIREMENTS_EXTRA=""

ENV PHP_CFLAGS="-fstack-protector-strong -fpic -fpie -O2" \
    PHP_CPPFLAGS="-fstack-protector-strong -fpic -fpie -O2" \
    PHP_LDFLAGS="-Wl,-O1 -Wl,--hash-style=both -pie" \
    PHP_VERSION="${PHP_VERSION}" \
    PHP_INI_DIR="/usr/local/etc/php" \
    PHP_SRC_DIR="/usr/src/php" \
    PHP_URL="https://www.php.net/distributions/php-${PHP_VERSION}.tar.xz"

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ${PHP_BUILD_REQUIREMENTS} ${PHP_BUILD_REQUIREMENTS_EXTRA} && \
    rm -rf /var/lib/apt/lists/*

# Download and extract PHP source
WORKDIR /usr/src
RUN curl -fsSL -o php.tar.xz "$PHP_URL" && \
    tar -xf php.tar.xz && \
    mv php-${PHP_VERSION} php && \
    rm php.tar.xz

# Configure and build PHP
WORKDIR /usr/src/php
RUN gnuArch="$(dpkg-architecture --query DEB_BUILD_GNU_TYPE)"; \
    debMultiarch="$(dpkg-architecture --query DEB_BUILD_MULTIARCH)"; \
    if [ ! -d "/usr/include/curl" ]; then \
        ln -sT "/usr/include/${debMultiarch}/curl" /usr/local/include/curl; \
    fi; \
    export CFLAGS="$PHP_CFLAGS" CPPFLAGS="$PHP_CPPFLAGS" LDFLAGS="$PHP_LDFLAGS"; \
    ./configure \
        --build="$gnuArch" \
        --with-config-file-path="$PHP_INI_DIR" \
        --with-config-file-scan-dir="$PHP_INI_DIR/conf.d" \
        --enable-option-checking=fatal \
        --disable-cgi \
        --with-pear \
        --with-pdo-mysql=mysqlnd \
        --enable-mysqlnd \
        --with-mhash \
        --enable-ftp \
        --enable-mbstring \
        --with-curl \
        --with-libedit \
        --with-openssl \
        --with-zlib \
        --enable-exif \
        --enable-bcmath \
        --enable-sockets \
        --with-xsl \
        --enable-pcntl \
        --with-sodium \
        --with-tidy \
        --enable-gd \
        --with-jpeg \
        --with-freetype \
        --enable-soap \
        --enable-intl \
        --enable-fpm \
        --with-fpm-user=www-data \
        --with-fpm-group=www-data && \
    make -j "$(nproc)" && \
    make install && \
    rm -rf /usr/src/php

# Runtime stage
FROM wilmadigital/php-base:bookworm-latest AS php

COPY FS /

ARG PHP_VERSION="8.2.30"
ARG PHP_RUNTIME_REQUIREMENTS="jq curl libcurl3-gnutls ca-certificates libedit2 libgmp-dev libfreetype6 libltdl7 libmcrypt4 sqlite3 libpng16-16 libzip4 libfcgi-bin libtidy5deb1 libsodium23 libonig5 cron zip libxml2 libxslt1.1 libssl3 zlib1g libreadline8 libicu72 libargon2-1"
ARG PHP_RUNTIME_REQUIREMENTS_EXTRA=""
ARG IMAGICK_VERSION="3.8.0"

ENV PHP_INI_DIR="/usr/local/etc/php" \
    PHP_VERSION="${PHP_VERSION}" \
    PHPIZE_BUILD_REQUIREMENTS="build-essential automake autoconf libtool file g++ gcc libc-dev make pkg-config re2c libltdl-dev" \
    DOCUMENT_ROOT="/var/www/html" \
    IMAGICK_VERSION="${IMAGICK_VERSION}"

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

# Copy compiled PHP from builder
COPY --from=builder /usr/local/ /usr/local/

# Install runtime dependencies and configure PHP
RUN set -xe && \
    chmod 755 /usr/local/bin/docker-entrypoint && \
    /usr/local/bin/docker-install-requirements php && \
    ln -fs /etc/alternatives/vi /usr/bin/vim && \
    mkdir -p "${PHP_INI_DIR}/conf.d" /tmp/mhsendmail /usr/src && \
    apt-get update && \
    apt-get install -y --no-install-recommends ${PHP_RUNTIME_REQUIREMENTS} ${PHP_RUNTIME_REQUIREMENTS_EXTRA} && \
    rm -rf /var/lib/apt/lists/*

# Install mhsendmail
RUN curl -fsSL -o /usr/local/bin/mhsendmail \
    'https://github.com/mailhog/mhsendmail/releases/download/v0.2.0/mhsendmail_linux_amd64' && \
    chmod +x /usr/local/bin/mhsendmail
# Install Node.js 22
RUN apt-get update && \
    apt-get install -y ca-certificates curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


# Install PHP extensions using PECL
RUN set -xe && \
    apt-get update && \
    apt-get install -y --no-install-recommends ${PHPIZE_BUILD_REQUIREMENTS} && \
    pecl install imagick && \
    pecl install redis && \
    pecl install igbinary && \
    echo "extension=imagick.so" > /usr/local/etc/php/conf.d/20-imagick.ini && \
    echo "extension=redis.so" > /usr/local/etc/php/conf.d/20-redis.ini && \
    echo "extension=igbinary.so" > /usr/local/etc/php/conf.d/20-igbinary.ini && \
    apt-get purge -y --auto-remove ${PHPIZE_BUILD_REQUIREMENTS} && \
    rm -rf /var/lib/apt/lists/*

# Configure PHP-FPM
RUN set -xe && \
    sed 's!=NONE/!=!g' /usr/local/etc/php-fpm.conf.default | tee /usr/local/etc/php-fpm.conf > /dev/null && \
    cp /usr/local/etc/php-fpm.d/www.conf.default /usr/local/etc/php-fpm.d/www.conf && \
    { \
        echo '[global]'; \
        echo 'error_log = /proc/self/fd/2'; \
        echo; \
        echo '[www]'; \
        echo 'access.log = /proc/self/fd/2'; \
        echo 'clear_env = no'; \
        echo 'catch_workers_output = yes'; \
    } | tee /usr/local/etc/php-fpm.d/docker.conf && \
    { \
        echo '[global]'; \
        echo 'daemonize = no'; \
        echo; \
        echo '[www]'; \
        echo 'listen = 9000'; \
        echo 'pm.max_children = 10'; \
        echo 'pm.min_spare_servers = 2'; \
        echo 'pm.max_spare_servers = 5'; \
        echo 'pm.status_path = /status'; \
    } | tee /usr/local/etc/php-fpm.d/zz-docker.conf

# Install Composer 2 and Magento tools (consolidated)
RUN set -xe && \
    COMPOSER_DOWNLOAD_LATEST=$(curl -s https://api.github.com/repos/composer/composer/releases/latest | jq --raw-output '.assets[] | .browser_download_url' | head -n 1) && \
    docker-package-download -o /usr/local/bin/composer ${COMPOSER_DOWNLOAD_LATEST} && \
    chmod +x /usr/local/bin/composer && \
    composer selfupdate && \
    curl -fsSL -o /usr/local/bin/magerun https://files.magerun.net/n98-magerun.phar && \
    chmod +x /usr/local/bin/magerun && \
    curl -fsSL -o /usr/local/bin/magerun2 https://files.magerun.net/n98-magerun2.phar && \
    chmod +x /usr/local/bin/magerun2 && \
    /usr/local/bin/docker-layer-clean

# Set up permissions for www-data user
RUN mkdir -p /var/www/html && \
    chown -R www-data:www-data /var/www/html && \
    chmod -R 755 /var/www/html

WORKDIR /var/www/html

# Health check for PHP-FPM status endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD pgrep -f "php-fpm: master process" > /dev/null || exit 1

ENTRYPOINT ["docker-entrypoint"]
CMD ["php-fpm"]
EXPOSE 9000

# Toolbox stage - includes development tools
FROM php AS toolbox

ARG TOOLBOX_RUNTIME_REQUIREMENTS="curl git redis-tools mariadb-client percona-toolkit rsync openssh-client vim.tiny php-xdebug"
ARG TOOLBOX_RUNTIME_REQUIREMENTS_EXTRA=""

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

# Install development tools including Composer 1 (legacy support)
RUN /usr/local/bin/docker-install-requirements toolbox && \
    apt-get update && \
    apt-get install -y --no-install-recommends ${TOOLBOX_RUNTIME_REQUIREMENTS} ${TOOLBOX_RUNTIME_REQUIREMENTS_EXTRA} && \
    rm -rf /var/lib/apt/lists/* && \
    curl https://rclone.org/install.sh | bash && \
    docker-package-download -o /usr/local/bin/composer1 https://getcomposer.org/composer-1.phar && \
    chmod +x /usr/local/bin/composer1 && \
    composer1 selfupdate && \
    composer require deployer/deployer && \
    composer update && \
    echo "export PATH=$PATH:/var/www/html/vendor/bin" >> /etc/profile && \
    echo "xdebug.mode=coverage" > /usr/local/etc/php/conf.d/xdebug-coverage.ini && \
    /usr/local/bin/docker-layer-clean

CMD ["php", "-a"]
