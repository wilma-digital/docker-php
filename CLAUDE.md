# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains Docker images for OpenMage PHP containers with automated version management. It supports PHP versions 8.2-8.5, each available with or without Node.js (versions 22, 24, 26). Images come in two variants: `php` (runtime) and `toolbox` (extended with development tools).

**Patch window per branch**: for each PHP minor we build only the most recent patch
releases — the last **5** for maintained branches (active or security support) and the last
**3** for EOL branches — driven by the `maintained` flag in `versions.json`. As of mid-2026
that is 8.2/8.3/8.4/8.5 (maintained, 5 each). `check-php-releases.py`
recomputes this sliding window from php.net, so old patches drop off as new ones ship.

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
context. Because the variants build `FROM` the published `php:<patch>` images, those images
must exist first: CI builds the base images on **Monday** (`php-<version>.yml`) and the Node
variants on **Tuesday** (`php-<version>-node.yml`), one day later. See "GitHub Actions".

### Base Image Matrix

- **PHP 8.2-8.4**: `wilmadigital/php-base:bookworm-latest` (Debian Bookworm)
- **PHP 8.5**: `wilmadigital/php-base:trixie-latest` (Debian Trixie)

The `base_image` in `versions.json` is **pinned by digest** (`tag@sha256:...`, the
multi-arch index digest) for reproducible builds and a stable compile cache. Re-pin the
digest when you want to pull in fresh base-OS security updates (a `docker buildx imagetools
inspect wilmadigital/php-base:<tag>` gives the current index digest).

### Build Optimizations

**Implemented optimizations**:
- Consolidated RUN commands (better layer caching)
- Explicit builder stage (reduces image size by ~500MB)
- PHP compiled once in the base image; Node variants layer on top (no recompile)
- **Native per-arch runners** for base builds (amd64 + arm64), no QEMU emulation — the
  arm64 PHP compile is native instead of ~5-10x slower emulated
- **Registry build cache** (`wilmadigital/php-cache`) instead of the 10 GB-capped GHA cache
- Base image pinned by digest → compile layer stays cache-stable across scheduled rebuilds
- PECL extensions and Composer/deployer pinned for reproducible builds
- `mhsendmail` installed arch-correctly (amd64 only, skipped on arm64)
- Composer downloaded from the stable `getcomposer.org` URL (no rate-limited GitHub API)
- Composer 1 only in toolbox stage, and only on PHP < 8.5

**Image size reduction**: ~650MB per image vs. previous approach

## Version Management

### Editing Versions

Edit `versions.json` to add/modify PHP versions or Node.js variants:

```json
{
  "versions": {
    "8.5": {
      "php_version": "8.5.8",
      "base_image": "wilmadigital/php-base:trixie-latest",
      "maintained": true,
      "patch_versions": [4, 5, 6, 7, 8],
      "php_runtime_libs": "...",
      "php_build_libs": "..."
    }
  },
  "node_versions": [22, 24, 26]
}
```

`patch_versions` holds the latest 5 patch releases from https://www.php.net/releases/ for
maintained branches (`"maintained": true`) and the latest 3 for EOL branches
(`"maintained": false`). `check-php-releases.py` maintains this window automatically.

#### Do not remove `patch` from `php_runtime_libs`

`patch` (GNU patch) looks like a build-time tool and is not one here. The predecessor
images (`openmage/php`) carried it by accident: `dpkg-dev` depends on it and everything
lived in a single layer. This build separates the builder and runtime stages and runs
`apt-get purge --auto-remove` on the build requirements, which takes `patch` with it —
which is why the 8.3.30 toolbox image shipped without it and nobody noticed.

Magento projects need it at install time. `cweagans/composer-patches` bails out of its
`git apply` path whenever `$install_path/.git` is missing, and a Composer dist package
such as `magento/framework` never has one — so the `patch` binary is the only path left.
Without it `composer install` fails with `Cannot apply patch … Skipping`, which reads
like a broken patch file rather than a missing package.

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
- `wilmadigital/php:8.5.12-node26` - PHP 8.5.12 + Node.js 26
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

Each PHP version has **two** workflows, deliberately decoupled onto consecutive days so the
Node variants build on top of already-published php images (and to spread Docker Hub load):

1. `.github/workflows/php-<version>.yml` — jobs `build-base` + `merge`. Compiles PHP.
   `build-base` runs each architecture on a **native runner** (`ubuntu-24.04` for amd64,
   `ubuntu-24.04-arm` for arm64), building the `php` and `toolbox` targets single-arch and
   pushing them **by digest** (`push-by-digest=true`, no tag). The `merge` job then assembles
   the multi-arch manifest tags (`php:<patch>`, `-toolbox`, and the rolling `<minor>` tags)
   from those digests via `docker buildx imagetools create`, and runs Trivy/SBOM/smoke on the
   final tags. Native runners avoid QEMU — the arm64 compile is ~5-10x faster. Scheduled
   **Monday**.
2. `.github/workflows/php-<version>-node.yml` — job `build-node`. Layers Node.js (22, 24, 26)
   on the published `php:<patch>` / `php:<patch>-toolbox` images — no PHP recompile, so it
   stays on a single multi-arch buildx (arm64 under QEMU is fine for an `apt` install).
   Scheduled **Tuesday** (staggered per version, same clock times as the base build).

There is intentionally **no** `needs:` between the two workflows: they are separate workflows
on separate schedules. If you ever want event-driven chaining instead of the one-day gap,
switch the node workflow's trigger to `on: workflow_run` completed for the base workflow.

Build cache is a **registry cache** in `wilmadigital/php-cache` (tagged per
version/patch/target/arch), not the GitHub Actions cache — the GHA cache's 10 GB/repo limit
thrashes across this many scopes. Combined with the digest-pinned base image, the compile
layer reuses cache across scheduled rebuilds.

> Requires GitHub-hosted **arm64 runners** (`ubuntu-24.04-arm`); on private repos these are
> billed. Verify availability for this repo before relying on the schedule.

**Images per patch**: base = 2 (php + toolbox); node = 6 (3 Node versions × php+node and
toolbox+node). With the current window (8.2/8.3/8.4/8.5×5 = 20 patches) that is
20×2 = 40 base images and 20×3×2 = 120 node images per full weekly cycle. The rolling
major.minor tags are aliases on the highest-patch build, not extra builds.

**Triggers** (each workflow):
- Push to main (its own source paths, relevant template, or `versions.json`)
- Manual trigger (workflow_dispatch)
- Weekly schedule (base Monday, node Tuesday)

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
for v in 8.2 8.3 8.4 8.5; do
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
- Versions: 22 (LTS), 24 (LTS), 26 (Current)

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
