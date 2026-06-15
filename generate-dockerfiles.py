#!/usr/bin/env python3
"""
Generate version-specific Dockerfiles from template.
"""

import json
import os
import sys
from pathlib import Path


def load_template(template_path: Path) -> str:
    """Load Dockerfile template."""
    with open(template_path, 'r') as f:
        return f.read()


def load_versions(versions_path: Path) -> dict:
    """Load version configuration."""
    with open(versions_path, 'r') as f:
        return json.load(f)


def substitute_template(template: str, variables: dict) -> str:
    """Substitute template variables."""
    result = template
    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, str(value))
    return result


def generate_dockerfile(template: str, php_version: str, config: dict) -> str:
    """Generate the base (PHP-only) Dockerfile from the compile template."""
    variables = {
        'PHP_VERSION': config['php_version'],
        'BASE_IMAGE': config['base_image'],
        'PHP_RUNTIME_LIBS': config['php_runtime_libs'],
        'PHP_BUILD_LIBS': config['php_build_libs']
    }

    return substitute_template(template, variables)


def generate_node_dockerfile(node_template: str, config: dict, node_version: int) -> str:
    """Generate a Node.js variant Dockerfile.

    Node variants do NOT recompile PHP. They layer Node.js on top of the
    prebuilt wilmadigital/php:${PHP_VERSION} image, so PHP is compiled exactly
    once (in the base image) and reused across every Node.js variant.
    """
    variables = {
        'PHP_VERSION': config['php_version'],
        'NODE_VERSION': node_version,
    }

    return substitute_template(node_template, variables)


def main():
    """Main function."""
    script_dir = Path(__file__).parent
    template_path = script_dir / 'Dockerfile.template'
    node_template_path = script_dir / 'Dockerfile.node.template'
    versions_path = script_dir / 'versions.json'

    if not template_path.exists():
        print(f"Error: Template not found at {template_path}", file=sys.stderr)
        sys.exit(1)

    if not node_template_path.exists():
        print(f"Error: Node template not found at {node_template_path}", file=sys.stderr)
        sys.exit(1)

    if not versions_path.exists():
        print(f"Error: Version config not found at {versions_path}", file=sys.stderr)
        sys.exit(1)

    template = load_template(template_path)
    node_template = load_template(node_template_path)
    config = load_versions(versions_path)

    versions = config['versions']
    node_versions = config.get('node_versions', [])

    print(f"Generating Dockerfiles for {len(versions)} PHP versions...")

    for php_version, version_config in versions.items():
        # Generate base Dockerfile (without Node.js)
        dockerfile_dir = script_dir / 'src' / php_version / 'src'
        dockerfile_dir.mkdir(parents=True, exist_ok=True)
        dockerfile_path = dockerfile_dir / 'Dockerfile'

        dockerfile_content = generate_dockerfile(template, php_version, version_config)

        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)

        print(f"✓ Generated {dockerfile_path}")

        # Generate Node.js variants.
        # These layer Node.js on the prebuilt php image and need no PHP source,
        # php.ini (FS/) or build context beyond the Dockerfile itself.
        if node_versions:
            for node_version in node_versions:
                node_dir = script_dir / 'src' / php_version / f'node{node_version}' / 'src'
                node_dir.mkdir(parents=True, exist_ok=True)
                node_dockerfile_path = node_dir / 'Dockerfile'

                # Remove any stale FS/ left over from the old compile-based
                # node variants - it is baked into the base php image now.
                # Best-effort: a leftover FS/ is unused, so never fail the run.
                fs_target = node_dir / 'FS'
                if fs_target.exists():
                    import shutil
                    shutil.rmtree(fs_target, ignore_errors=True)

                dockerfile_content = generate_node_dockerfile(
                    node_template, version_config, node_version)

                with open(node_dockerfile_path, 'w') as f:
                    f.write(dockerfile_content)

                print(f"✓ Generated {node_dockerfile_path}")

    print(f"\nSuccessfully generated all Dockerfiles!")
    print(f"\nNext steps:")
    print(f"1. Review the generated Dockerfiles")
    print(f"2. Update GitHub Actions workflows for Node.js matrix")
    print(f"3. Test builds locally")


if __name__ == '__main__':
    main()
