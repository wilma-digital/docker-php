#!/usr/bin/env python3
"""
Generate GitHub Actions workflow files from versions.json.

Each PHP version produces TWO workflows:

  * php-<version>.yml       - base fpm + toolbox images.
                              Scheduled on Mondays.
  * php-<version>-node.yml  - Node.js variants layered on the published
                              toolbox image (no PHP rebuild). Chained via
                              workflow_run: starts after a successful php-<version>
                              run, so the toolbox image always exists first.

Registry: images are pushed to ghcr.io/wilma-digital/php (primary, pushed with
GITHUB_TOKEN, no pull limits) and mirrored to docker.io/wilmadigital/php while
consumers migrate.

Rebuild rule: every patch release is built ONCE and then frozen. The weekly
schedule only rebuilds the newest patch per minor (base OS security updates).
A push to main builds the newest patch plus every patch in the window that does
not exist on ghcr yet; a manual dispatch with rebuild_all rebuilds the window.

Base images build each architecture on a NATIVE runner (ubuntu-24.04 for amd64,
ubuntu-24.04-arm for arm64), push each by digest, and a `merge` job assembles the
multi-arch manifest tags. Node variants only run `apt-get install nodejs`, so
they stay on a single multi-arch buildx.

Build cache uses a registry (ghcr.io/wilma-digital/php-cache) instead of the
GitHub Actions cache, whose 10 GB/repo limit thrashes across this large matrix.
"""

import json
from pathlib import Path

IMAGE = "ghcr.io/wilma-digital/php"
MIRROR = "docker.io/wilmadigital/php"
CACHE_REPO = "ghcr.io/wilma-digital/php-cache"

# Base images build on Monday (cron day-of-week 1), staggered to avoid rate limits.
BASE_SCHEDULE = {
    '8.2': '30 7 * * 1',
    '8.3': '00 8 * * 1',
    '8.4': '30 8 * * 1',
    '8.5': '00 9 * * 1',
}

# Native runners per architecture (no QEMU emulation).
PLATFORMS = [
    ('amd64', 'ubuntu-24.04'),
    ('arm64', 'ubuntu-24.04-arm'),
]

# Extensions every image built on the official php base must ship
# (compiled-in ones plus what install-php-extensions adds).
OFFICIAL_EXTENSIONS = [
    'apcu', 'bcmath', 'bz2', 'exif', 'gd', 'gmp', 'igbinary', 'imagick', 'intl',
    'mysqli', 'pcntl', 'pdo_mysql', 'redis', 'soap', 'sockets', 'sodium', 'tidy',
    'xsl', 'zip', 'Zend OPcache',
]

LOGIN_STEPS = """      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Login to DockerHub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_HUB_USERNAME }}
          password: ${{ secrets.DOCKER_HUB_ACCESS_TOKEN }}
"""


def load_versions(versions_path: Path) -> dict:
    with open(versions_path, 'r') as f:
        return json.load(f)


def _per_arch_build_step(target: str) -> str:
    """A build-push (push-by-digest) + digest-save step pair for one target."""
    return f"""      - name: Build and push {target} image by digest
        id: build-{target}
        uses: docker/build-push-action@v6
        with:
          platforms: linux/${{{{ matrix.platform.arch }}}}
          context: ./src/${{{{ matrix.version }}}}/src
          file: ./src/${{{{ matrix.version }}}}/src/Dockerfile
          target: {target}
          provenance: false
          build-args: |
            PHP_VERSION=${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
          outputs: type=image,name={IMAGE},push-by-digest=true,name-canonical=true,push=true
          cache-from: type=registry,ref={CACHE_REPO}:${{{{ matrix.version }}}}-${{{{ matrix.patchVersion }}}}-{target}-${{{{ matrix.platform.arch }}}}
          cache-to: type=registry,ref={CACHE_REPO}:${{{{ matrix.version }}}}-${{{{ matrix.patchVersion }}}}-{target}-${{{{ matrix.platform.arch }}}},mode=max

      - name: Export {target} digest
        run: |
          mkdir -p /tmp/digests/{target}
          echo "${{{{ steps.build-{target}.outputs.digest }}}}" > "/tmp/digests/{target}/${{{{ matrix.platform.arch }}}}"
"""


def _merge_manifest_step(name: str, tags: list, rolling_tags: list, latest_patch: int, target: str) -> str:
    """Assemble a multi-arch manifest on ghcr and the Docker Hub mirror.

    `tags` are written for every patch (X.Y.Z...), `rolling_tags` (X.Y...) only
    for the newest patch of the window.
    """
    fixed = ' '.join(tags)
    rolling = ' '.join(rolling_tags)
    return f"""      - name: Create {name} manifest
        env:
          V: ${{{{ matrix.version }}}}
          P: ${{{{ matrix.patchVersion }}}}
        run: |
          NAMES="{fixed}"
          if [ "$P" = "{latest_patch}" ]; then
            NAMES="$NAMES {rolling}"
          fi
          TAGS=()
          for n in $NAMES; do
            TAGS+=(-t "{IMAGE}:$n" -t "{MIRROR}:$n")
          done
          docker buildx imagetools create "${{TAGS[@]}}" \\
            "{IMAGE}@$(cat /tmp/digests/{target}/amd64)" \\
            "{IMAGE}@$(cat /tmp/digests/{target}/arm64)"
"""


def _scan_and_sbom(image_ref: str, kind: str, slug: str) -> str:
    """Trivy scan + SBOM + upload for a final (merged, already pulled) image tag.

    File names use the static `kind`: an `if:` that embeds ${{ }} in a string
    is always true. `slug` (may contain expressions) names the uploads.
    """
    return f"""      - name: Trivy scan {kind}
        uses: aquasecurity/trivy-action@master
        continue-on-error: true
        with:
          image-ref: {image_ref}
          format: 'sarif'
          output: 'trivy-{kind}.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Upload Trivy results for {kind}
        uses: github/codeql-action/upload-sarif@v3
        if: always() && hashFiles('trivy-{kind}.sarif') != ''
        with:
          sarif_file: 'trivy-{kind}.sarif'
          category: 'trivy-{slug}'

      - name: Generate SBOM for {kind}
        uses: anchore/sbom-action@v0
        continue-on-error: true
        with:
          image: {image_ref}
          format: spdx-json
          output-file: 'sbom-{kind}.spdx.json'

      - name: Upload SBOM for {kind}
        uses: actions/upload-artifact@v4
        if: always() && hashFiles('sbom-{kind}.spdx.json') != ''
        with:
          name: 'sbom-{slug}'
          path: 'sbom-{kind}.spdx.json'
          retention-days: 90
"""


def _smoke_test_step(php_ref: str, toolbox_ref: str, official: bool) -> str:
    if official:
        exts = ' '.join(f"'{e}'" for e in OFFICIAL_EXTENSIONS)
        ext_check = f"""          MODULES="$(docker run --rm {php_ref} php -m)"
          for ext in {exts}; do
            grep -qx "$ext" <<<"$MODULES" || {{ echo "missing extension: $ext"; exit 1; }}
          done
          docker run --rm {toolbox_ref} php -m | grep -x xdebug >/dev/null && {{ echo "xdebug must be off by default"; exit 1; }}
          docker run --rm -e PHP_EXT_ENABLE="xdebug pcov" {toolbox_ref} php -m | grep -x xdebug >/dev/null
          docker run --rm -e PHP_EXT_ENABLE="xdebug pcov" {toolbox_ref} php -m | grep -x pcov >/dev/null"""
    else:
        ext_check = f"""          docker run --rm {php_ref} php -m | grep -E "redis|imagick|opcache\""""
    return f"""      - name: Smoke test images
        shell: bash
        run: |
          set -euo pipefail
          docker pull {php_ref}
          docker pull {toolbox_ref}
          docker run --rm {php_ref} php -v
          docker run --rm {php_ref} composer --version
          docker run --rm {php_ref} which patch
{ext_check}
"""


def generate_base_workflow(version: str, version_config: dict) -> str:
    patch_versions = version_config['patch_versions']
    official = version_config.get('build') == 'official'
    template = 'Dockerfile.official.template' if official else 'Dockerfile.template'
    patch_str = ', '.join(str(p) for p in patch_versions)
    patch_words = ' '.join(str(p) for p in patch_versions)
    latest_patch = max(patch_versions)
    cron_time = BASE_SCHEDULE.get(version, '00 7 * * 1')

    platforms_yaml = '\n'.join(
        f"          - arch: {arch}\n            runner: {runner}"
        for arch, runner in PLATFORMS
    )

    php_ref = IMAGE + ":${{ matrix.version }}.${{ matrix.patchVersion }}-fpm"
    toolbox_ref = IMAGE + ":${{ matrix.version }}.${{ matrix.patchVersion }}-toolbox"

    return f"""name: "{version}"
on:
  workflow_dispatch:
    inputs:
      rebuild_all:
        description: 'Rebuild every patch in the window, not only new ones and the newest'
        type: boolean
        default: false
  push:
    branches:
      - main
    paths:
      - 'src/{version}/src/**'
      - '.github/workflows/php-{version}.yml'
      - '{template}'
      - 'versions.json'
  schedule:
    - cron: '{cron_time}'

permissions:
  contents: read
  packages: write
  security-events: write
  actions: read

# Prevent parallel workflow runs to avoid Docker Hub rate limits
concurrency:
  group: php-{version}-base
  cancel-in-progress: false

jobs:
  plan:
    name: "Select patches to build"
    runs-on: ubuntu-24.04
    outputs:
      patches: ${{{{ steps.select.outputs.patches }}}}
    steps:
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{{{ github.actor }}}}
          password: ${{{{ secrets.GITHUB_TOKEN }}}}

      # Patches are built once and then frozen. Weekly runs refresh only the
      # newest patch; pushes add patches that are not on ghcr yet.
      - name: Select patches
        id: select
        env:
          EVENT: ${{{{ github.event_name }}}}
          REBUILD_ALL: ${{{{ inputs.rebuild_all }}}}
        run: |
          if [ "$EVENT" = "schedule" ]; then
            SELECTED="{latest_patch}"
          elif [ "$REBUILD_ALL" = "true" ]; then
            SELECTED="{patch_words}"
          else
            SELECTED=""
            for p in {patch_words}; do
              if [ "$p" = "{latest_patch}" ] || ! docker buildx imagetools inspect "{IMAGE}:{version}.$p-fpm" >/dev/null 2>&1; then
                SELECTED="$SELECTED $p"
              fi
            done
          fi
          PATCHES="[$(echo "$SELECTED" | xargs | tr ' ' ',')]"
          echo "Building {version} patches: $PATCHES (window: [{patch_str}])"
          echo "patches=$PATCHES" >> "$GITHUB_OUTPUT"

  build-base:
    name: "PHP ${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}} (${{{{ matrix.platform.arch }}}})"
    needs: plan
    runs-on: ${{{{ matrix.platform.runner }}}}
    strategy:
      fail-fast: false
      matrix:
        version: ['{version}']
        patchVersion: ${{{{ fromJSON(needs.plan.outputs.patches) }}}}
        platform:
{platforms_yaml}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

{LOGIN_STEPS}
{_per_arch_build_step('php')}
{_per_arch_build_step('toolbox')}
      - name: Upload digests
        uses: actions/upload-artifact@v4
        with:
          name: digests-${{{{ matrix.patchVersion }}}}-${{{{ matrix.platform.arch }}}}
          path: /tmp/digests/**
          retention-days: 1

  merge:
    name: "Merge PHP ${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}"
    needs: [plan, build-base]
    runs-on: ubuntu-24.04
    strategy:
      fail-fast: false
      matrix:
        version: ['{version}']
        patchVersion: ${{{{ fromJSON(needs.plan.outputs.patches) }}}}
    steps:
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

{LOGIN_STEPS}
      - name: Download digests
        uses: actions/download-artifact@v4
        with:
          pattern: digests-${{{{ matrix.patchVersion }}}}-*
          path: /tmp/digests
          merge-multiple: true

{_merge_manifest_step('fpm', ['$V.$P', '$V.$P-fpm'], ['$V', '$V-fpm'], latest_patch, 'php')}
{_merge_manifest_step('toolbox', ['$V.$P-toolbox'], ['$V-toolbox'], latest_patch, 'toolbox')}
{_smoke_test_step(php_ref, toolbox_ref, official)}
{_scan_and_sbom(php_ref, 'php', 'php-' + version + '.${{ matrix.patchVersion }}')}
{_scan_and_sbom(toolbox_ref, 'toolbox', 'toolbox-' + version + '.${{ matrix.patchVersion }}')}"""


def generate_node_workflow(version: str, version_config: dict, node_versions: list) -> str:
    node_str = ', '.join(str(n) for n in node_versions)
    latest_patch = max(version_config['patch_versions'])
    php_full = f"{version}.{latest_patch}"
    ref = f"{IMAGE}:{php_full}-toolbox-node${{{{ matrix.nodeVersion }}}}"

    # Node variants exist only for the toolbox and only on the newest patch.
    # X.Y-nodeNN-toolbox is the pre-ghcr tag name, kept as an alias.
    tags = '\n'.join(
        f"            {registry}:{name}"
        for registry in (IMAGE, MIRROR)
        for name in (
            f"{php_full}-toolbox-node${{{{ matrix.nodeVersion }}}}",
            f"{version}-toolbox-node${{{{ matrix.nodeVersion }}}}",
            f"{version}-node${{{{ matrix.nodeVersion }}}}-toolbox",
        )
    )

    return f"""name: "{version}-node"
on:
  workflow_dispatch:
  # Chained after the base workflow: the variants build FROM its toolbox image.
  # Covers the weekly refresh and every base change (templates, versions.json).
  workflow_run:
    workflows: ["{version}"]
    types: [completed]
    branches: [main]
  push:
    branches:
      - main
    paths:
      - 'src/{version}/node*/**'
      - '.github/workflows/php-{version}-node.yml'

permissions:
  contents: read
  packages: write
  security-events: write
  actions: read

# Prevent parallel workflow runs to avoid Docker Hub rate limits
concurrency:
  group: php-{version}-node
  cancel-in-progress: false

jobs:
  plan:
    name: "Check base toolbox image"
    if: github.event_name != 'workflow_run' || github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-24.04
    outputs:
      ready: ${{{{ steps.check.outputs.ready }}}}
    steps:
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{{{ github.actor }}}}
          password: ${{{{ secrets.GITHUB_TOKEN }}}}

      # A push can change the base and the node files at once (e.g. a patch bump).
      # Then the base image may not be on ghcr yet; the run chained after
      # php-{version} builds the variants instead of failing here.
      - name: Check {IMAGE}:{php_full}-toolbox
        id: check
        env:
          EVENT: ${{{{ github.event_name }}}}
        run: |
          if docker buildx imagetools inspect "{IMAGE}:{php_full}-toolbox" >/dev/null 2>&1; then
            echo "ready=true" >> "$GITHUB_OUTPUT"
          elif [ "$EVENT" = "push" ]; then
            echo "::notice::{php_full}-toolbox is not on ghcr yet, the run after workflow {version} builds the Node variants."
            echo "ready=false" >> "$GITHUB_OUTPUT"
          else
            echo "::error::{IMAGE}:{php_full}-toolbox not found, run workflow {version} first."
            exit 1
          fi

  build-node:
    name: "PHP {php_full} toolbox + Node ${{{{ matrix.nodeVersion }}}}"
    needs: plan
    if: needs.plan.outputs.ready == 'true'
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        nodeVersion: [{node_str}]
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          # workflow_run: build the commit the base images were built from
          ref: ${{{{ github.event.workflow_run.head_sha || github.sha }}}}

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

{LOGIN_STEPS}
      - name: Build and push toolbox+node image
        uses: docker/build-push-action@v6
        with:
          push: true
          platforms: linux/amd64,linux/arm64
          tags: |
{tags}
          context: ./src/{version}/node${{{{ matrix.nodeVersion }}}}/src
          file: ./src/{version}/node${{{{ matrix.nodeVersion }}}}/src/Dockerfile
          target: toolbox
          build-args: |
            BASE_IMAGE={IMAGE}
            PHP_VERSION={php_full}
            NODE_VERSION=${{{{ matrix.nodeVersion }}}}
          cache-from: type=registry,ref={CACHE_REPO}:{version}-node${{{{ matrix.nodeVersion }}}}-toolbox
          cache-to: type=registry,ref={CACHE_REPO}:{version}-node${{{{ matrix.nodeVersion }}}}-toolbox,mode=max

      - name: Smoke test toolbox+node image
        run: |
          docker pull {ref}
          docker run --rm {ref} php -v
          docker run --rm {ref} node -v
          docker run --rm {ref} npm -v

{_scan_and_sbom(ref, 'toolbox-node', 'toolbox-' + php_full + '-node${{ matrix.nodeVersion }}')}"""


def main():
    script_dir = Path(__file__).parent
    versions_path = script_dir / 'versions.json'
    workflows_dir = script_dir / '.github' / 'workflows'

    config = load_versions(versions_path)
    versions = config['versions']
    node_versions = config.get('node_versions', [])

    print(f"Generating workflow files for {len(versions)} PHP versions...")

    for version, version_config in versions.items():
        base_path = workflows_dir / f'php-{version}.yml'
        with open(base_path, 'w') as f:
            f.write(generate_base_workflow(version, version_config))
        print(f"✓ Generated {base_path}")

        node_path = workflows_dir / f'php-{version}-node.yml'
        with open(node_path, 'w') as f:
            f.write(generate_node_workflow(version, version_config, node_versions))
        print(f"✓ Generated {node_path}")

    print("\nSuccessfully generated all workflow files!")


if __name__ == '__main__':
    main()
