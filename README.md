# OpenMage PHP Container

Production-ready PHP-FPM Docker images optimized for OpenMage/Magento, with optional Node.js support.

## Features

- **Multiple PHP versions**: 8.1, 8.2, 8.3, 8.4, 8.5
- **Node.js variants**: Optional Node.js 22, 24, or 25 LTS
- **Two image types**: Runtime (`php`) and Development (`toolbox`)
- **Multi-architecture**: AMD64 and ARM64 support
- **Automated updates**: Weekly checks for new PHP releases
- **Template-based**: Single Dockerfile template for all versions
- **Security hardening**: Non-root user, vulnerability scanning, SBOM generation
- **Production-ready**: Health checks, smoke tests, resource recommendations

## Available Images

### Base PHP Images

| Tag                          | Description                |
|------------------------------|----------------------------|
| `wilmadigital/php:8.5.3`         | PHP 8.5.3 runtime (latest) |
| `wilmadigital/php:8.5.3-toolbox` | PHP 8.5.3 with dev tools   |
| `wilmadigital/php:8.4.18`        | PHP 8.4.18 runtime         |
| `wilmadigital/php:8.3.29`        | PHP 8.3.29 runtime         |
| `wilmadigital/php:8.2.30`        | PHP 8.2.30 runtime         |
| `wilmadigital/php:8.1.34`        | PHP 8.1.34 runtime         |

### Node.js Variants

| Tag                                 | Description                    |
|-------------------------------------|--------------------------------|
| `wilmadigital/php:8.5.3-node22`         | PHP 8.5.3 + Node.js 22 LTS     |
| `wilmadigital/php:8.5.3-node24`         | PHP 8.5.3 + Node.js 24 LTS     |
| `wilmadigital/php:8.5.3-node25`         | PHP 8.5.3 + Node.js 25 Current |
| `wilmadigital/php:8.5.3-node22-toolbox` | With development tools         |

All combinations available for PHP 8.1-8.5 with Node.js 22, 24, 25.

## Quick Start

### Basic Usage

```dockerfile
FROM wilmadigital/php:8.5.3

COPY . /var/www/html
WORKDIR /var/www/html

# Your application setup
RUN composer install --no-dev --optimize-autoloader
```

### With Node.js (for frontend builds)

```dockerfile
FROM wilmadigital/php:8.5.3-node22

COPY . /var/www/html
WORKDIR /var/www/html

# Install PHP dependencies
RUN composer install --no-dev --optimize-autoloader

# Install Node.js dependencies
RUN npm ci --production
```

### Development with Toolbox

```dockerfile
FROM wilmadigital/php:8.5.3-toolbox

# Includes: xdebug, deployer, rclone, git, composer 1+2, magerun
```

## What's Included

### Runtime Stage (`php`)

**PHP Extensions**:
- imagick (ImageMagick support)
- redis (Redis caching)
- igbinary (efficient data serialization)
- opcache (bytecode cache, 512MB)
- gd (image processing)
- Standard: PDO, MySQLi, curl, soap, intl, bcmath, sockets, xsl, pcntl, sodium, tidy

**Tools**:
- Composer 2 (latest)
- n98-magerun (Magento 1 CLI)
- n98-magerun2 (Magento 2 CLI)
- mhsendmail (MailHog integration)

**Configuration**:
- PHP-FPM on port 9000
- Production php.ini included
- Optimized for OpenMage/Magento workloads

### Toolbox Stage (`toolbox`)

Everything from runtime stage, plus:

- Composer 1 (legacy support)
- xdebug (with coverage mode)
- Deployer (deployment tool)
- rclone (cloud storage sync)
- git, redis-tools, mariadb-client
- percona-toolkit, rsync, openssh-client

### Node.js Variants

- Node.js installed via NodeSource APT repository
- npm updated to latest version
- Available in standard PATH

## Usage Examples

### Docker Compose

```yaml
version: '3.8'

services:
  php:
    image: wilmadigital/php:8.5.3
    volumes:
      - ./:/var/www/html
    ports:
      - "9000:9000"
    environment:
      - PHP_INI_SCAN_DIR=/usr/local/etc/php/conf.d

  php-node:
    image: wilmadigital/php:8.5.3-node22
    volumes:
      - ./:/var/www/html
    command: sh -c "npm install && composer install"
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openmage-php
spec:
  replicas: 3
  selector:
    matchLabels:
      app: openmage
  template:
    metadata:
      labels:
        app: openmage
    spec:
      containers:
      - name: php-fpm
        image: wilmadigital/php:8.5.3
        ports:
        - containerPort: 9000
        resources:
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### Building Frontend Assets

```bash
# Use Node.js variant for asset compilation
docker run --rm -v $(pwd):/app -w /app \
  wilmadigital/php:8.5.3-node22 \
  sh -c "npm install && npm run build"
```

### Running Magerun

```bash
# OpenMage (Magento 1)
docker run --rm -v $(pwd):/var/www/html \
  wilmadigital/php:8.5.3 \
  magerun cache:flush

# Magento 2
docker run --rm -v $(pwd):/var/www/html \
  wilmadigital/php:8.5.3 \
  magerun2 cache:clean
```

## PHP Configuration

Production-optimized settings included:

```ini
memory_limit = -1                # Unlimited (for CLI operations)
max_execution_time = 600         # 10 minutes
max_input_time = 300             # 5 minutes
max_input_vars = 200000          # For large forms
post_max_size = 8M
upload_max_filesize = 5M

opcache.enable = 1
opcache.memory_consumption = 512
opcache.max_accelerated_files = 65406
```

Override with custom php.ini:
```dockerfile
FROM wilmadigital/php:8.5.3
COPY custom-php.ini /usr/local/etc/php/conf.d/custom.ini
```

## Development

### Local Build

```bash
# Clone repository
git clone https://github.com/wilma-digital/docker-php.git
cd docker-php

# Build specific version
docker build -f src/8.5/src/Dockerfile -t my-php:8.5 src/8.5/src/

# Build with Node.js
docker build -f src/8.5/node22/src/Dockerfile -t my-php:8.5-node22 src/8.5/node22/src/
```

### Template System

This repository uses a template-based build system:

```bash
# Edit the template
vim Dockerfile.template

# Edit version configuration
vim versions.json

# Regenerate all Dockerfiles
./generate-dockerfiles.py

# Regenerate workflows
./generate-workflows.py
```

### Automated Updates

The repository automatically checks for new PHP releases weekly:

- **Schedule**: Every Monday at 8 AM UTC
- **Action**: Creates PR with updated versions
- **Includes**: Regenerated Dockerfiles and workflows

Manual check:
```bash
./check-php-releases.py
```

## Security & Compliance

### Security Features

- **Non-Root User**: All containers run as `www-data` (UID 33)
- **Vulnerability Scanning**: Trivy scans on every build (CRITICAL/HIGH)
- **SBOM Generation**: Software Bill of Materials in SPDX JSON format
- **Dependency Review**: Automated scanning on pull requests
- **Supply Chain Security**: License compliance checks
- **Health Checks**: Built-in container health monitoring
- **Smoke Tests**: Automated verification of PHP, extensions, and tools

### Compliance

- SBOM artifacts available for all images (90-day retention)
- SARIF vulnerability reports uploaded to GitHub Security
- Denied licenses: GPL-3.0, AGPL-3.0
- Security advisories monitored via Dependabot

See [PRODUCTION.md](PRODUCTION.md) for detailed security configuration and best practices.

## Version Support

| PHP Version | Status         | EOL Date      |
|-------------|----------------|---------------|
| 8.5         | Active         | TBD           |
| 8.4         | Active         | TBD           |
| 8.3         | Active         | November 2026 |
| 8.2         | Active         | December 2025 |
| 8.1         | Security fixes | November 2025 |

## Architecture

- **Base Images**: Debian Bookworm (8.1-8.4), Debian Trixie (8.5)
- **PHP-FPM**: Compiled from source with custom configure flags
- **Multi-stage**: Optimized 3-stage build (builder → runtime → toolbox)
- **Platforms**: linux/amd64, linux/arm64

## Resources

- **PHP Releases**: https://www.php.net/releases/
- **Node.js Releases**: https://nodejs.org/en/about/previous-releases
- **Imagick Tags**: https://github.com/Imagick/imagick/tags
- **Docker Hub**: https://hub.docker.com/r/wilmadigital/php

## Contributing

1. Fork the repository
2. Edit `Dockerfile.template` or `versions.json`
3. Run `./generate-dockerfiles.py && ./generate-workflows.py`
4. Test locally
5. Submit pull request

## License

[Your License]

## Changelog

### 2025-04-01
- Implemented template-based build system
- Added Node.js variants (22, 24, 25)
- Automated PHP release detection
- Moved Composer 1 to toolbox only
- Optimized multi-stage builds (~650MB reduction)
- Added registry caching for faster rebuilds

### Previous
- Initial PHP 8.1-8.5 support
- Multi-architecture builds (AMD64, ARM64)
- Toolbox variant with development tools
