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


def add_nodejs_support(dockerfile: str, node_version: int) -> str:
    """Add Node.js installation to Dockerfile."""
    # Add Node.js installation after runtime dependencies
    # Using new NodeSource repository method (2023+)
    nodejs_install = f"""
# Install Node.js {node_version}
RUN apt-get update && \\
    apt-get install -y ca-certificates curl gnupg && \\
    mkdir -p /etc/apt/keyrings && \\
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \\
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_{node_version}.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \\
    apt-get update && \\
    apt-get install -y nodejs && \\
    npm install -g npm@latest && \\
    apt-get clean && \\
    rm -rf /var/lib/apt/lists/*
"""

    # Insert after the runtime dependencies installation
    insert_after = "rm -rf /var/lib/apt/lists/*"
    parts = dockerfile.split(insert_after, 1)

    if len(parts) == 2:
        return parts[0] + insert_after + nodejs_install + parts[1]
    return dockerfile


def generate_dockerfile(template: str, php_version: str, config: dict, node_version: int = None) -> str:
    """Generate a version-specific Dockerfile."""
    variables = {
        'PHP_VERSION': config['php_version'],
        'BASE_IMAGE': config['base_image'],
        'PHP_RUNTIME_LIBS': config['php_runtime_libs'],
        'PHP_BUILD_LIBS': config['php_build_libs']
    }

    dockerfile = substitute_template(template, variables)

    if node_version:
        dockerfile = add_nodejs_support(dockerfile, node_version)

    return dockerfile


def main():
    """Main function."""
    script_dir = Path(__file__).parent
    template_path = script_dir / 'Dockerfile.template'
    versions_path = script_dir / 'versions.json'

    if not template_path.exists():
        print(f"Error: Template not found at {template_path}", file=sys.stderr)
        sys.exit(1)

    if not versions_path.exists():
        print(f"Error: Version config not found at {versions_path}", file=sys.stderr)
        sys.exit(1)

    template = load_template(template_path)
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

        # Generate Node.js variants
        if node_versions:
            for node_version in node_versions:
                node_dir = script_dir / 'src' / php_version / f'node{node_version}' / 'src'
                node_dir.mkdir(parents=True, exist_ok=True)
                node_dockerfile_path = node_dir / 'Dockerfile'

                # Copy FS directory if it doesn't exist
                fs_source = dockerfile_dir / 'FS'
                fs_target = node_dir / 'FS'

                if fs_source.exists() and not fs_target.exists():
                    import shutil
                    shutil.copytree(fs_source, fs_target)

                dockerfile_content = generate_dockerfile(template, php_version, version_config, node_version)

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
