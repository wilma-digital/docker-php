#!/usr/bin/env python3
"""
Check for new PHP releases and update versions.json.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
import urllib.request
from urllib.error import URLError


def fetch_php_releases() -> Optional[List[Dict]]:
    """Fetch PHP releases from php.net API."""
    try:
        url = "https://www.php.net/releases/index.php?json&max=100"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = response.read()
            return json.loads(data)
    except (URLError, json.JSONDecodeError) as e:
        print(f"Error fetching PHP releases: {e}", file=sys.stderr)
        return None


def parse_version(version_str: str) -> Optional[tuple]:
    """Parse version string into tuple (major, minor, patch)."""
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)', version_str)
    if match:
        return tuple(map(int, match.groups()))
    return None


def get_latest_patch_version(releases: List[Dict], major: int, minor: int) -> Optional[str]:
    """Get the latest patch version for a given major.minor version."""
    matching_versions = []

    for version_key, release_data in releases.items():
        parsed = parse_version(version_key)
        if parsed and parsed[0] == major and parsed[1] == minor:
            matching_versions.append((parsed[2], version_key))

    if matching_versions:
        # Return version with highest patch number
        matching_versions.sort(reverse=True)
        return matching_versions[0][1]

    return None


def check_for_updates(config_path: Path) -> tuple[bool, Dict]:
    """Check if there are updates available for configured PHP versions."""
    with open(config_path, 'r') as f:
        config = json.load(f)

    releases = fetch_php_releases()
    if not releases:
        print("Failed to fetch PHP releases", file=sys.stderr)
        return False, config

    versions = config['versions']
    updated = False

    for version_key, version_config in versions.items():
        current_version = version_config['php_version']
        parsed = parse_version(current_version)

        if not parsed:
            continue

        major, minor, patch = parsed

        # Get latest patch version for this major.minor
        latest = get_latest_patch_version(releases, major, minor)

        if latest and latest != current_version:
            parsed_latest = parse_version(latest)
            if parsed_latest and parsed_latest[2] > patch:
                print(f"✓ Update available for PHP {version_key}: {current_version} → {latest}")
                version_config['php_version'] = latest
                updated = True

                # Update patch_versions array to include new patch
                current_patches = version_config.get('patch_versions', [])
                new_patch = parsed_latest[2]
                if new_patch not in current_patches:
                    current_patches.append(new_patch)
                    current_patches.sort()
                    version_config['patch_versions'] = current_patches
            else:
                print(f"  PHP {version_key}: {current_version} (up to date)")
        else:
            print(f"  PHP {version_key}: {current_version} (up to date)")

    return updated, config


def main():
    """Main function."""
    script_dir = Path(__file__).parent
    config_path = script_dir / 'versions.json'

    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}", file=sys.stderr)
        sys.exit(1)

    print("Checking for PHP release updates...")
    updated, new_config = check_for_updates(config_path)

    if updated:
        # Write updated configuration
        with open(config_path, 'w') as f:
            json.dump(new_config, f, indent=2)
            f.write('\n')

        print("\n✓ versions.json has been updated")
        print("\nNext steps:")
        print("1. Run generate-dockerfiles.py to regenerate Dockerfiles")
        print("2. Run generate-workflows.py to regenerate workflows")
        print("3. Test the builds locally")
        print("4. Commit and push changes")

        # Exit with code 1 to indicate updates were found
        sys.exit(1)
    else:
        print("\n✓ All PHP versions are up to date")
        sys.exit(0)


if __name__ == '__main__':
    main()
