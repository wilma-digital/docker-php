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


def generate_official_dockerfile(template: str, config: dict) -> str:
    """Generate the base Dockerfile from the official php image template."""
    variables = {
        'PHP_VERSION': config['php_version'],
        'DEBIAN_CODENAME': config['debian'],
    }

    return substitute_template(template, variables)


def sync_official_fs(script_dir: Path, dockerfile_dir: Path) -> None:
    """Copy the shared helper scripts (entrypoint etc.) into the build context.

    The official php image lacks the helpers that wilmadigital/php-base used to
    provide, so they live once in FS.official/ and are copied next to php.ini.
    """
    import shutil
    shutil.copytree(script_dir / 'FS.official', dockerfile_dir / 'FS', dirs_exist_ok=True)


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
    official_template_path = script_dir / 'Dockerfile.official.template'
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
    official_template = load_template(official_template_path)
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

        # "build": "official" starts from php:X.Y.Z-fpm-<debian>; everything
        # else still compiles PHP on top of wilmadigital/php-base.
        if version_config.get('build') == 'official':
            dockerfile_content = generate_official_dockerfile(official_template, version_config)
            sync_official_fs(script_dir, dockerfile_dir)
        else:
            dockerfile_content = generate_dockerfile(template, php_version, version_config)

        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)

        print(f"✓ Generated {dockerfile_path}")

        # Remove node<X> directories for Node.js versions no longer configured
        # (e.g. after dropping 25 in favour of 26), so the tree stays in sync.
        import shutil
        php_dir = script_dir / 'src' / php_version
        if php_dir.exists():
            keep = {f'node{n}' for n in node_versions}
            for child in php_dir.iterdir():
                if child.is_dir() and child.name.startswith('node') and child.name not in keep:
                    print(f"  ✗ Removing stale variant dir {child}")
                    shutil.rmtree(child, ignore_errors=True)

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
