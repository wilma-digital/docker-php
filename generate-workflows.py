#!/usr/bin/env python3
"""
Generate GitHub Actions workflow files from versions.json.

Each PHP version produces TWO workflows:

  * php-<version>.yml       - base php + toolbox images (compiles PHP).
                              Scheduled on Mondays.
  * php-<version>-node.yml  - Node.js variants layered on the published php
                              images (no PHP recompile). Scheduled on Tuesdays,
                              the day AFTER the base images are built.

Base images build PHP from source, which is the expensive step. To avoid slow
QEMU emulation of arm64, the base workflow builds each architecture on a NATIVE
runner (ubuntu-24.04 for amd64, ubuntu-24.04-arm for arm64), pushes each by
digest, and a `merge` job assembles the multi-arch manifest tags. Node variants
only run `apt-get install nodejs`, so they stay on a single multi-arch buildx.

Build cache uses a registry (wilmadigital/php-cache) instead of the GitHub
Actions cache, whose 10 GB/repo limit thrashes across this large matrix. With
the base image pinned by digest in versions.json, the compile layer stays cache-
stable, so scheduled rebuilds reuse it instead of recompiling.
"""

import json
from pathlib import Path

CACHE_REPO = "wilmadigital/php-cache"

# Base images build on Monday (cron day-of-week 1), staggered to avoid rate limits.
BASE_SCHEDULE = {
    '8.1': '00 7 * * 1',
    '8.2': '30 7 * * 1',
    '8.3': '00 8 * * 1',
    '8.4': '30 8 * * 1',
    '8.5': '00 9 * * 1',
}

# Node variants build on Tuesday (cron day-of-week 2), one day after the base images.
NODE_SCHEDULE = {
    '8.1': '00 7 * * 2',
    '8.2': '30 7 * * 2',
    '8.3': '00 8 * * 2',
    '8.4': '30 8 * * 2',
    '8.5': '00 9 * * 2',
}

# Native runners per architecture (no QEMU emulation).
PLATFORMS = [
    ('amd64', 'ubuntu-24.04'),
    ('arm64', 'ubuntu-24.04-arm'),
]


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
          outputs: type=image,name=wilmadigital/php,push-by-digest=true,name-canonical=true,push=true
          cache-from: type=registry,ref={CACHE_REPO}:${{{{ matrix.version }}}}-${{{{ matrix.patchVersion }}}}-{target}-${{{{ matrix.platform.arch }}}}
          cache-to: type=registry,ref={CACHE_REPO}:${{{{ matrix.version }}}}-${{{{ matrix.patchVersion }}}}-{target}-${{{{ matrix.platform.arch }}}},mode=max

      - name: Export {target} digest
        run: |
          mkdir -p /tmp/digests/{target}
          echo "${{{{ steps.build-{target}.outputs.digest }}}}" > "/tmp/digests/{target}/${{{{ matrix.platform.arch }}}}"
"""


def _merge_manifest_step(name: str, tag_suffix: str, latest_patch: int, target: str) -> str:
    """Assemble a multi-arch manifest tag (+ rolling tag on the highest patch)."""
    # tag_suffix is '' for php or '-toolbox' for toolbox.
    return f"""      - name: Create {name} manifest
        run: |
          TAGS="-t wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}{tag_suffix}"
          if [ "${{{{ matrix.patchVersion }}}}" = "{latest_patch}" ]; then
            TAGS="$TAGS -t wilmadigital/php:${{{{ matrix.version }}}}{tag_suffix}"
          fi
          docker buildx imagetools create $TAGS \\
            wilmadigital/php@$(cat /tmp/digests/{target}/amd64) \\
            wilmadigital/php@$(cat /tmp/digests/{target}/arm64)
"""


def _scan_and_sbom(image_ref: str, slug: str) -> str:
    """Trivy scan + SBOM + upload for a final (merged) image tag."""
    return f"""      - name: Trivy scan {slug}
        uses: aquasecurity/trivy-action@master
        continue-on-error: true
        with:
          image-ref: {image_ref}
          format: 'sarif'
          output: 'trivy-{slug}.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Upload Trivy results for {slug}
        uses: github/codeql-action/upload-sarif@v3
        if: always() && hashFiles('trivy-{slug}.sarif') != ''
        with:
          sarif_file: 'trivy-{slug}.sarif'
          category: 'trivy-{slug}'

      - name: Generate SBOM for {slug}
        uses: anchore/sbom-action@v0
        continue-on-error: true
        with:
          image: {image_ref}
          format: spdx-json
          output-file: 'sbom-{slug}.spdx.json'

      - name: Upload SBOM for {slug}
        uses: actions/upload-artifact@v4
        if: always() && hashFiles('sbom-{slug}.spdx.json') != ''
        with:
          name: 'sbom-{slug}'
          path: 'sbom-{slug}.spdx.json'
          retention-days: 90
"""


def generate_base_workflow(version: str, patch_versions: list) -> str:
    patch_str = ', '.join(str(p) for p in patch_versions)
    latest_patch = max(patch_versions)
    cron_time = BASE_SCHEDULE.get(version, '00 7 * * 1')

    platforms_yaml = '\n'.join(
        f"          - arch: {arch}\n            runner: {runner}"
        for arch, runner in PLATFORMS
    )

    php_ref = "wilmadigital/php:${{ matrix.version }}.${{ matrix.patchVersion }}"
    toolbox_ref = php_ref + "-toolbox"

    return f"""name: "{version}"
on:
  workflow_dispatch:
  push:
    branches:
      - main
    paths:
      - 'src/{version}/src/**'
      - '.github/workflows/php-{version}.yml'
      - 'Dockerfile.template'
      - 'versions.json'
  schedule:
    - cron: '{cron_time}'

permissions:
  contents: read
  security-events: write
  actions: read

# Prevent parallel workflow runs to avoid Docker Hub rate limits
concurrency:
  group: php-{version}-base
  cancel-in-progress: false

jobs:
  build-base:
    name: "PHP ${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}} (${{{{ matrix.platform.arch }}}})"
    runs-on: ${{{{ matrix.platform.runner }}}}
    strategy:
      fail-fast: false
      matrix:
        version: ['{version}']
        patchVersion: [{patch_str}]
        platform:
{platforms_yaml}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to DockerHub
        uses: docker/login-action@v3
        with:
          username: ${{{{ secrets.DOCKER_HUB_USERNAME }}}}
          password: ${{{{ secrets.DOCKER_HUB_ACCESS_TOKEN }}}}

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
    needs: build-base
    runs-on: ubuntu-24.04
    strategy:
      fail-fast: false
      matrix:
        version: ['{version}']
        patchVersion: [{patch_str}]
    steps:
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to DockerHub
        uses: docker/login-action@v3
        with:
          username: ${{{{ secrets.DOCKER_HUB_USERNAME }}}}
          password: ${{{{ secrets.DOCKER_HUB_ACCESS_TOKEN }}}}

      - name: Download digests
        uses: actions/download-artifact@v4
        with:
          pattern: digests-${{{{ matrix.patchVersion }}}}-*
          path: /tmp/digests
          merge-multiple: true

{_merge_manifest_step('php', '', latest_patch, 'php')}
{_merge_manifest_step('toolbox', '-toolbox', latest_patch, 'toolbox')}
      - name: Smoke test php image
        run: |
          docker pull {php_ref}
          docker run --rm {php_ref} php -v
          docker run --rm {php_ref} php -m | grep -E "redis|imagick|opcache"
          docker run --rm {php_ref} composer --version

{_scan_and_sbom(php_ref, 'php-' + version + '.${{ matrix.patchVersion }}')}
{_scan_and_sbom(toolbox_ref, 'toolbox-' + version + '.${{ matrix.patchVersion }}')}"""


def generate_node_workflow(version: str, patch_versions: list, node_versions: list) -> str:
    patch_str = ', '.join(str(p) for p in patch_versions)
    node_str = ', '.join(str(n) for n in node_versions)
    latest_patch = max(patch_versions)
    cron_time = NODE_SCHEDULE.get(version, '00 7 * * 2')

    return f"""name: "{version}-node"
on:
  workflow_dispatch:
  push:
    branches:
      - main
    paths:
      - 'src/{version}/node*/**'
      - '.github/workflows/php-{version}-node.yml'
      - 'Dockerfile.node.template'
      - 'versions.json'
  schedule:
    # Runs the day after the base php-{version} images are built.
    - cron: '{cron_time}'

permissions:
  contents: read
  security-events: write
  actions: read

# Prevent parallel workflow runs to avoid Docker Hub rate limits
concurrency:
  group: php-{version}-node
  cancel-in-progress: false

jobs:
  build-node:
    name: "PHP ${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}} + Node ${{{{ matrix.nodeVersion }}}}"
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        version: ['{version}']
        patchVersion: [{patch_str}]
        nodeVersion: [{node_str}]
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to DockerHub
        uses: docker/login-action@v3
        with:
          username: ${{{{ secrets.DOCKER_HUB_USERNAME }}}}
          password: ${{{{ secrets.DOCKER_HUB_ACCESS_TOKEN }}}}

      - name: Build and push php+node image
        uses: docker/build-push-action@v6
        with:
          push: true
          platforms: linux/amd64,linux/arm64
          tags: |
            wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
            ${{{{ matrix.patchVersion == {latest_patch} && format('wilmadigital/php:{{0}}-node{{1}}', matrix.version, matrix.nodeVersion) || '' }}}}
          context: ./src/${{{{ matrix.version }}}}/node${{{{ matrix.nodeVersion }}}}/src
          file: ./src/${{{{ matrix.version }}}}/node${{{{ matrix.nodeVersion }}}}/src/Dockerfile
          target: php
          build-args: |
            PHP_VERSION=${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
            NODE_VERSION=${{{{ matrix.nodeVersion }}}}
          cache-from: type=registry,ref={CACHE_REPO}:${{{{ matrix.version }}}}-${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          cache-to: type=registry,ref={CACHE_REPO}:${{{{ matrix.version }}}}-${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}},mode=max

      - name: Trivy scan php+node
        uses: aquasecurity/trivy-action@master
        continue-on-error: true
        with:
          image-ref: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          format: 'sarif'
          output: 'trivy-node.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Upload Trivy results for php+node
        uses: github/codeql-action/upload-sarif@v3
        if: always() && hashFiles('trivy-node.sarif') != ''
        with:
          sarif_file: 'trivy-node.sarif'
          category: 'trivy-node-${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}'

      - name: Generate SBOM for php+node
        uses: anchore/sbom-action@v0
        continue-on-error: true
        with:
          image: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          format: spdx-json
          output-file: sbom-node.spdx.json

      - name: Upload SBOM for php+node
        uses: actions/upload-artifact@v4
        if: always() && hashFiles('sbom-node.spdx.json') != ''
        with:
          name: sbom-node-${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          path: sbom-node.spdx.json
          retention-days: 90

      - name: Smoke test php+node image
        run: |
          docker pull wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          docker run --rm wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}} php -v
          docker run --rm wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}} node -v
          docker run --rm wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}} npm -v

      - name: Build and push toolbox+node image
        uses: docker/build-push-action@v6
        with:
          push: true
          platforms: linux/amd64,linux/arm64
          tags: |
            wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}-toolbox
            ${{{{ matrix.patchVersion == {latest_patch} && format('wilmadigital/php:{{0}}-node{{1}}-toolbox', matrix.version, matrix.nodeVersion) || '' }}}}
          context: ./src/${{{{ matrix.version }}}}/node${{{{ matrix.nodeVersion }}}}/src
          file: ./src/${{{{ matrix.version }}}}/node${{{{ matrix.nodeVersion }}}}/src/Dockerfile
          target: toolbox
          build-args: |
            PHP_VERSION=${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
            NODE_VERSION=${{{{ matrix.nodeVersion }}}}
          cache-from: type=registry,ref={CACHE_REPO}:${{{{ matrix.version }}}}-${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}-toolbox
          cache-to: type=registry,ref={CACHE_REPO}:${{{{ matrix.version }}}}-${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}-toolbox,mode=max

      - name: Trivy scan toolbox+node
        uses: aquasecurity/trivy-action@master
        continue-on-error: true
        with:
          image-ref: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}-toolbox
          format: 'sarif'
          output: 'trivy-toolbox-node.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Upload Trivy results for toolbox+node
        uses: github/codeql-action/upload-sarif@v3
        if: always() && hashFiles('trivy-toolbox-node.sarif') != ''
        with:
          sarif_file: 'trivy-toolbox-node.sarif'
          category: 'trivy-toolbox-node-${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}'

      - name: Generate SBOM for toolbox+node
        uses: anchore/sbom-action@v0
        continue-on-error: true
        with:
          image: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}-toolbox
          format: spdx-json
          output-file: sbom-toolbox-node.spdx.json

      - name: Upload SBOM for toolbox+node
        uses: actions/upload-artifact@v4
        if: always() && hashFiles('sbom-toolbox-node.spdx.json') != ''
        with:
          name: sbom-toolbox-node-${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          path: sbom-toolbox-node.spdx.json
          retention-days: 90
"""


def main():
    script_dir = Path(__file__).parent
    versions_path = script_dir / 'versions.json'
    workflows_dir = script_dir / '.github' / 'workflows'

    config = load_versions(versions_path)
    versions = config['versions']
    node_versions = config.get('node_versions', [])

    print(f"Generating workflow files for {len(versions)} PHP versions...")

    for version, version_config in versions.items():
        patch_versions = version_config.get('patch_versions', [0, 1, 2, 3])

        base_path = workflows_dir / f'php-{version}.yml'
        with open(base_path, 'w') as f:
            f.write(generate_base_workflow(version, patch_versions))
        print(f"✓ Generated {base_path}")

        node_path = workflows_dir / f'php-{version}-node.yml'
        with open(node_path, 'w') as f:
            f.write(generate_node_workflow(version, patch_versions, node_versions))
        print(f"✓ Generated {node_path}")

    print("\nSuccessfully generated all workflow files!")


if __name__ == '__main__':
    main()
