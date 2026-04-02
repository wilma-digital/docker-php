#!/usr/bin/env python3
"""
Generate GitHub Actions workflow files from template.
"""

import json
from pathlib import Path


def load_versions(versions_path: Path) -> dict:
    """Load version configuration."""
    with open(versions_path, 'r') as f:
        return json.load(f)


def generate_workflow(version: str, patch_versions: list, node_versions: list) -> str:
    """Generate workflow file content."""
    patch_str = ', '.join(str(p) for p in patch_versions)
    node_str = ', '.join(str(n) for n in node_versions)

    workflow = f"""name: "{version}"
on:
  workflow_dispatch:
  push:
    branches:
      - main
    paths:
      - 'src/{version}/**'
      - '.github/workflows/php-{version}.yml'
      - 'Dockerfile.template'
      - 'versions.json'
  schedule:
    - cron: '00 7 * * 1'

permissions:
  contents: read
  security-events: write
  actions: read

jobs:
  build-base:
    name: "PHP ${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}"
    runs-on: ubuntu-latest
    strategy:
      matrix:
        version: ['{version}']
        patchVersion: [{patch_str}]
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

      - name: Build and push php image
        uses: docker/build-push-action@v6
        with:
          push: true
          platforms: linux/amd64,linux/arm64
          tags: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
          context: ./src/${{{{ matrix.version }}}}/src
          file: ./src/${{{{ matrix.version }}}}/src/Dockerfile
          target: php
          build-args: |
            PHP_VERSION=${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
          cache-from: type=registry,ref=wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
          cache-to: type=inline

      - name: Run Trivy vulnerability scanner on php image
        uses: aquasecurity/trivy-action@master
        continue-on-error: true
        with:
          image-ref: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Upload Trivy results to GitHub Security tab
        uses: github/codeql-action/upload-sarif@v3
        if: always() && hashFiles('trivy-results.sarif') != ''
        with:
          sarif_file: 'trivy-results.sarif'

      - name: Generate SBOM for php image
        uses: anchore/sbom-action@v0
        with:
          image: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
          format: spdx-json
          output-file: sbom-php.spdx.json

      - name: Upload SBOM as artifact
        uses: actions/upload-artifact@v4
        with:
          name: sbom-php-${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
          path: sbom-php.spdx.json
          retention-days: 90

      - name: Smoke test php image
        run: |
          docker pull wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
          echo "→ Testing PHP version..."
          docker run --rm wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}} php -v
          echo "→ Testing PHP extensions..."
          docker run --rm wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}} php -m | grep -E "redis|imagick|opcache"
          echo "→ Testing Composer..."
          docker run --rm wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}} composer --version
          echo "✓ All smoke tests passed"

      - name: Build and push toolbox image
        uses: docker/build-push-action@v6
        with:
          push: true
          platforms: linux/amd64,linux/arm64
          tags: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-toolbox
          context: ./src/${{{{ matrix.version }}}}/src
          file: ./src/${{{{ matrix.version }}}}/src/Dockerfile
          target: toolbox
          build-args: |
            PHP_VERSION=${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
          cache-from: type=registry,ref=wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-toolbox
          cache-to: type=inline

      - name: Run Trivy vulnerability scanner on toolbox image
        uses: aquasecurity/trivy-action@master
        continue-on-error: true
        with:
          image-ref: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-toolbox
          format: 'sarif'
          output: 'trivy-results-toolbox.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Upload Trivy results for toolbox to GitHub Security tab
        uses: github/codeql-action/upload-sarif@v3
        if: always() && hashFiles('trivy-results-toolbox.sarif') != ''
        with:
          sarif_file: 'trivy-results-toolbox.sarif'

      - name: Generate SBOM for toolbox image
        uses: anchore/sbom-action@v0
        with:
          image: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-toolbox
          format: spdx-json
          output-file: sbom-toolbox.spdx.json

      - name: Upload SBOM as artifact
        uses: actions/upload-artifact@v4
        with:
          name: sbom-toolbox-${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
          path: sbom-toolbox.spdx.json
          retention-days: 90

  build-node:
    name: "PHP ${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}} + Node ${{{{ matrix.nodeVersion }}}}"
    runs-on: ubuntu-latest
    strategy:
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
          tags: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          context: ./src/${{{{ matrix.version }}}}/node${{{{ matrix.nodeVersion }}}}/src
          file: ./src/${{{{ matrix.version }}}}/node${{{{ matrix.nodeVersion }}}}/src/Dockerfile
          target: php
          build-args: |
            PHP_VERSION=${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
          cache-from: type=registry,ref=wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          cache-to: type=inline

      - name: Run Trivy vulnerability scanner on php+node image
        uses: aquasecurity/trivy-action@master
        continue-on-error: true
        with:
          image-ref: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          format: 'sarif'
          output: 'trivy-results-node.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Upload Trivy results for php+node to GitHub Security tab
        uses: github/codeql-action/upload-sarif@v3
        if: always() && hashFiles('trivy-results-node.sarif') != ''
        with:
          sarif_file: 'trivy-results-node.sarif'

      - name: Generate SBOM for php+node image
        uses: anchore/sbom-action@v0
        with:
          image: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          format: spdx-json
          output-file: sbom-node.spdx.json

      - name: Upload SBOM as artifact
        uses: actions/upload-artifact@v4
        with:
          name: sbom-node-${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          path: sbom-node.spdx.json
          retention-days: 90

      - name: Smoke test php+node image
        run: |
          docker pull wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          echo "→ Testing PHP version..."
          docker run --rm wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}} php -v
          echo "→ Testing Node.js..."
          docker run --rm wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}} node -v
          echo "→ Testing npm..."
          docker run --rm wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}} npm -v
          echo "✓ All smoke tests passed"

      - name: Build and push toolbox+node image
        uses: docker/build-push-action@v6
        with:
          push: true
          platforms: linux/amd64,linux/arm64
          tags: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}-toolbox
          context: ./src/${{{{ matrix.version }}}}/node${{{{ matrix.nodeVersion }}}}/src
          file: ./src/${{{{ matrix.version }}}}/node${{{{ matrix.nodeVersion }}}}/src/Dockerfile
          target: toolbox
          build-args: |
            PHP_VERSION=${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}
          cache-from: type=registry,ref=wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}-toolbox
          cache-to: type=inline

      - name: Run Trivy vulnerability scanner on toolbox+node image
        uses: aquasecurity/trivy-action@master
        continue-on-error: true
        with:
          image-ref: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}-toolbox
          format: 'sarif'
          output: 'trivy-results-toolbox-node.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Upload Trivy results for toolbox+node to GitHub Security tab
        uses: github/codeql-action/upload-sarif@v3
        if: always() && hashFiles('trivy-results-toolbox-node.sarif') != ''
        with:
          sarif_file: 'trivy-results-toolbox-node.sarif'

      - name: Generate SBOM for toolbox+node image
        uses: anchore/sbom-action@v0
        with:
          image: wilmadigital/php:${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}-toolbox
          format: spdx-json
          output-file: sbom-toolbox-node.spdx.json

      - name: Upload SBOM as artifact
        uses: actions/upload-artifact@v4
        with:
          name: sbom-toolbox-node-${{{{ matrix.version }}}}.${{{{ matrix.patchVersion }}}}-node${{{{ matrix.nodeVersion }}}}
          path: sbom-toolbox-node.spdx.json
          retention-days: 90
"""
    return workflow


def main():
    """Main function."""
    script_dir = Path(__file__).parent
    versions_path = script_dir / 'versions.json'
    workflows_dir = script_dir / '.github' / 'workflows'

    config = load_versions(versions_path)
    versions = config['versions']
    node_versions = config.get('node_versions', [])

    print(f"Generating workflow files for {len(versions)} PHP versions...")

    for version, version_config in versions.items():
        workflow_path = workflows_dir / f'php-{version}.yml'
        patch_versions = version_config.get('patch_versions', [0, 1, 2, 3])

        workflow_content = generate_workflow(version, patch_versions, node_versions)

        with open(workflow_path, 'w') as f:
            f.write(workflow_content)

        print(f"✓ Generated {workflow_path}")

    print("\nSuccessfully generated all workflow files!")


if __name__ == '__main__':
    main()
