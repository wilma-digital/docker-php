# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains Docker images for OpenMage PHP containers with automated version management. It supports PHP versions 8.1-8.5, each available with or without Node.js (versions 22, 24, 25). Images come in two variants: `php` (runtime) and `toolbox` (extended with development tools).

## Architecture

### Template-Based Build System

The repository uses a **template-based system** to eliminate duplication:

```
├── Dockerfile.template       # Source of truth for the base php/toolbox images (compiles PHP)
├── Dockerfile.node.template  # Source of truth for the Node.js variants (layers Node on the php image)
├── versions.json             # Version configuration (PHP + Node.js)
├── generate-dockerfiles.py   # Generates version-specific Dockerfiles
├── generate-workflows.py     # Generates GitHub Actions workflows
├── check-php-releases.py     # Automated PHP release detection
└── src/
    ├── 8.1/
    │   ├── src/             # PHP 8.1 base
    │   ├── node22/src/      # PHP 8.1 + Node.js 22
    │   ├── node24/src/      # PHP 8.1 + Node.js 24
    │   └── node25/src/      # PHP 8.1 + Node.js 25
    ├── 8.2/
    ├── 8.3/
    ├── 8.4/
    └── 8.5/
```

**Key Principle**: Never edit Dockerfiles directly - always edit the appropriate template (`Dockerfile.template` for base images, `Dockerfile.node.template` for Node variants) and regenerate.

### Multi-Stage Build

**Base images** (`Dockerfile.template`) use an optimized 3-stage build:

1. **Builder Stage**: Compiles PHP from source with optimized flags
   - Isolated build dependencies
   - Parallel compilation with `make -j $(nproc)`
   - Minimal layer count for better caching

2. **PHP Stage (runtime)**: Production-ready PHP-FPM
   - Copies only compiled binaries from builder
   - Essential extensions: imagick, redis, igbinary, opcache, gd
   - Tools: Composer 2, magerun, magerun2
   - Composer 1 removed from runtime (moved to toolbox)

3. **Toolbox Stage**: Development/deployment tools
   - Extends PHP stage
   - Additional tools: git, redis-tools, mariadb-client, deployer, rclone
   - Composer 1 (legacy support)
   - xdebug with coverage mode

**Node.js variants** (`Dockerfile.node.template`) do **not** recompile PHP. Each variant
layers Node.js (via the NodeSource APT repo) directly on top of the already-built base
images: the `php` target is `FROM wilmadigital/php:${PHP_VERSION}` and the `toolbox` target
is `FROM wilmadigital/php:${PHP_VERSION}-toolbox`. PHP is therefore compiled exactly once
(in the base image) and reused across all Node.js variants. The variant Dockerfile needs no
PHP source, no `FS/` (php.ini is baked into the base image) and only the Dockerfile as build
context. Because of this dependency, CI builds the base images first (`build-node` declares
`needs: build-base`).

### Base Image Matrix

- **PHP 8.1-8.4**: `wilmadigital/php-base:bookworm-latest` (Debian Bookworm)
- **PHP 8.5**: `wilmadigital/php-base:trixie-latest` (Debian Trixie)

### Build Optimizations

**Implemented optimizations**:
- Consolidated RUN commands (better layer caching)
- Explicit builder stage (reduces image size by ~500MB)
- Removed pickle.phar after extension installation
- Removed redundant chmod operations
- Fixed package duplication
- Registry caching enabled for faster rebuilds
- Composer 1 only in toolbox stage

**Image size reduction**: ~650MB per image vs. previous approach

## Version Management

### Editing Versions

Edit `versions.json` to add/modify PHP versions or Node.js variants:

```json
{
  "versions": {
    "8.5": {
      "php_version": "8.5.3",
      "base_image": "wilmadigital/php-base:trixie-latest",
      "patch_versions": [0, 1, 2, 3],
      "php_runtime_libs": "...",
      "php_build_libs": "..."
    }
  },
  "node_versions": [22, 24, 25]
}
```

With patch_versions being the latest 5 minor Release versions from https://www.php.net/releases/ for maintained versions and latst 3 versions from EOL versions.

### Regenerating Build Files

After editing `versions.json` or `Dockerfile.template`:

```bash
# Regenerate all Dockerfiles
./generate-dockerfiles.py

# Regenerate all workflow files
./generate-workflows.py
```

### Automated PHP Release Detection

The repository automatically checks for new PHP releases:

```bash
# Manual check
./check-php-releases.py

# Automated via GitHub Actions (weekly)
# → Creates PR with updates when new releases detected
```

**Workflow**: Every Monday at 8 AM UTC
- Checks PHP releases API
- Updates `versions.json` if newer patch versions exist
- Regenerates Dockerfiles and workflows
- Creates pull request with changes

## Building Images

### Local Testing (Single Architecture)

```bash
# Base PHP image
docker build -f src/8.5/src/Dockerfile -t wilmadigital/php:8.5.1 src/8.5/src/

# PHP + Node.js variant
docker build -f src/8.5/node22/src/Dockerfile -t wilmadigital/php:8.5.1-node22 src/8.5/node22/src/

# Toolbox variant
docker build --target toolbox -t wilmadigital/php:8.5.1-toolbox src/8.5/src/
```

### Multi-Architecture Build and Push

```bash
cd src/8.5/src

# Create buildx builder (one-time setup)
docker buildx create --use

# Build and push
docker buildx build --progress=plain \
  --platform linux/amd64,linux/arm64 \
  --push \
  -t wilmadigital/php:8.5.1 .
```

### Build Targets

```bash
# Runtime stage
docker build --target php -t wilmadigital/php:8.5.1 .

# Toolbox stage
docker build --target toolbox -t wilmadigital/php:8.5.1-toolbox .
```

## Image Tags

**Base PHP images**:
- `wilmadigital/php:8.5.1` - PHP 8.5.1 runtime
- `wilmadigital/php:8.5.1-toolbox` - With development tools

**Node.js variants**:
- `wilmadigital/php:8.5.1-node22` - PHP 8.5.1 + Node.js 22
- `wilmadigital/php:8.5.1-node24` - PHP 8.5.1 + Node.js 24
- `wilmadigital/php:8.5.1-node25` - PHP 8.5.1 + Node.js 25
- `wilmadigital/php:8.5.1-node22-toolbox` - With development tools

**Rolling major.minor tags** (always point to the highest patch built for that minor):
- `wilmadigital/php:8.5` - latest 8.5.x runtime
- `wilmadigital/php:8.5-toolbox` - latest 8.5.x toolbox
- `wilmadigital/php:8.5-node22` - latest 8.5.x + Node.js 22
- `wilmadigital/php:8.5-node22-toolbox` - latest 8.5.x + Node.js 22 + tools

Downstream projects should pin the rolling `8.5` (etc.) tag to pick up patch releases
automatically without editing anything. The rolling tag is published only by the build for
the highest patch in `versions.json` → `patch_versions`.

## GitHub Actions Workflows

### Version-Specific Workflows

Each PHP version has a workflow (`.github/workflows/php-8.X.yml`):

**Two build jobs**:
1. `build-base`: Builds PHP-only images (php + toolbox)
2. `build-node`: Builds Node.js variants (3 versions × 2 targets = 6 images). Runs **after**
   `build-base` (`needs: build-base`) because the variants layer on the freshly pushed
   `wilmadigital/php:<patch>` images rather than recompiling PHP.

**Total images per PHP version**: 8 (2 base + 6 Node.js variants)

**Triggers**:
- Push to main (version-specific paths, template, or config changes)
- Manual trigger (workflow_dispatch)
- Weekly schedule (Monday 7 AM UTC)

### Automatic Release Check Workflow

`.github/workflows/check-releases.yml`:
- Runs weekly (Monday 8 AM UTC)
- Checks PHP.net API for new releases
- Creates PR if updates found
- Includes regenerated Dockerfiles and workflows

### Pull Request Workflow

Runs hadolint linting on all Dockerfiles for PRs targeting main.

## Dockerfile Linting

```bash
# Lint specific version
docker run --rm -i pipelinecomponents/hadolint:latest < src/8.5/src/Dockerfile

# Lint all base versions
for v in 8.1 8.2 8.3 8.4 8.5; do
  echo "Linting PHP $v..."
  docker run --rm -i pipelinecomponents/hadolint:latest < src/$v/src/Dockerfile
done
```

## Version Updates

**Manual updates**:

1. Edit `versions.json`
2. Update PHP version or add new major.minor version
3. Regenerate files:
   ```bash
   ./generate-dockerfiles.py
   ./generate-workflows.py
   ```
4. Test locally
5. Commit and push

**Automated updates** (via PR):
- Weekly check creates PR
- Review versions.json changes
- Merge to trigger builds

## PHP Configuration

Production `php.ini` highlights:
- `memory_limit = -1` (unlimited)
- `max_execution_time = 600`
- `max_input_vars = 200000`
- `post_max_size = 8M`
- `upload_max_filesize = 5M`
- OPcache: 512MB, 65406 max files
- Error display: off, logging: on

## Node.js Support

Node.js is installed via NodeSource APT repository:
- Latest npm installed globally
- Available in PATH
- Versions: 22 (LTS), 24 (LTS), 25 (Current)

**Usage**:
```dockerfile
FROM wilmadigital/php:8.5.1-node22
# Node.js 22 and npm available
RUN node --version && npm --version
```

## Common Tasks

### Adding a New PHP Major Version

1. Edit `versions.json`:
   ```json
   "8.6": {
     "php_version": "8.6.0",
     "base_image": "wilmadigital/php-base:trixie-latest",
     "patch_versions": [0],
     "php_runtime_libs": "...",
     "php_build_libs": "..."
   }
   ```

2. Regenerate:
   ```bash
   ./generate-dockerfiles.py
   ./generate-workflows.py
   ```

3. Create `src/8.6/src/FS/` directory with php.ini

4. Test build locally

### Adding a New Node.js Version

1. Edit `versions.json`:
   ```json
   "node_versions": [22, 24, 25, 26]
   ```

2. Regenerate:
   ```bash
   ./generate-dockerfiles.py
   ./generate-workflows.py
   ```

### Modifying Dockerfile Logic

1. Edit `Dockerfile.template`
2. Regenerate all Dockerfiles:
   ```bash
   ./generate-dockerfiles.py
   ```
3. Test one version locally
4. Commit template + regenerated Dockerfiles

### Testing Before Push

```bash
# Test PHP 8.5 build
docker build -f src/8.5/src/Dockerfile -t test-php:8.5 src/8.5/src/

# Test PHP 8.5 + Node 22
docker build -f src/8.5/node22/src/Dockerfile -t test-php:8.5-node22 src/8.5/node22/src/

# Run container
docker run --rm -it test-php:8.5 php -v

# Test Node.js
docker run --rm -it test-php:8.5-node22 sh -c "php -v && node -v && npm -v"
```

## Troubleshooting

### Build fails with "pickle: command not found"

Ensure pickle is installed before extension installation in template.

### Node.js variant build fails

Check NodeSource repository is accessible and Node version exists.

### Workflow not triggering

Verify paths in workflow file match actual source directories.

### Release checker creates PR but no updates

Check if PHP API is accessible and version parsing is correct.

## Security and Compliance

### Phase 2 & 3 Security Features

**Implemented security measures**:

1. **Container Hardening**:
   - Non-root user (www-data, UID 33)
   - Health checks for all images
   - Minimal attack surface

2. **Vulnerability Scanning**:
   - Trivy scanning (CRITICAL/HIGH) on every build
   - SARIF results uploaded to GitHub Security
   - Dependency Review on all PRs

3. **Software Bill of Materials (SBOM)**:
   - Generated for all image variants
   - Format: SPDX JSON
   - Stored as GitHub Actions artifacts (90-day retention)
   - Download: `gh run download <run-id> -n sbom-php-8.5.3`

4. **Supply Chain Security**:
   - Automated dependency review
   - License compliance checks (deny GPL-3.0, AGPL-3.0)
   - Security advisories monitoring

5. **Smoke Tests**:
   - PHP version verification
   - Extension availability (redis, imagick, opcache)
   - Composer functionality
   - Node.js/npm verification (where applicable)

### Health Checks

All images include built-in health checks:
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD pgrep -f "php-fpm: master process" > /dev/null || exit 1
```

Use in production environments (see PRODUCTION.md for details).

## Production Deployment

See **PRODUCTION.md** for comprehensive production deployment guide including:
- Resource limits recommendations
- Health check configuration
- Security best practices
- Scaling strategies
- Monitoring and logging
- Performance tuning

## Resources

- PHP releases: https://www.php.net/releases/
- Node.js releases: https://nodejs.org/en/about/previous-releases
- Imagick: https://github.com/Imagick/imagick/tags
- Docker Hub: https://hub.docker.com/r/wilmadigital/php
- Production Guide: PRODUCTION.md

## Notes

- All images are multi-architecture: linux/amd64, linux/arm64
- Images published to Docker Hub under `wilmadigital` organization
- PHP-FPM runs on port 9000
- Default working directory: `/var/www/html`
- PHP-FPM config: 10 max children, 2-5 spare servers
- Status endpoint: `/status`
- Container runs as www-data user (UID 33)
- Health checks enabled by default
