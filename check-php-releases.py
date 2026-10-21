#!/usr/bin/env python3
"""
Check for new PHP releases and update versions.json.

For each configured PHP branch we keep a sliding window of the most recently
released patch versions:
  - maintained branches (active or security support): last 5 patches
  - EOL branches:                                     last 3 patches

The window (and php_version = highest patch) is recomputed from php.net on
every run, so old patches drop off automatically as new ones are released.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
import urllib.request
from urllib.error import URLError

MAINTAINED_PATCHES = 5
EOL_PATCHES = 3


def window_size(version_config: Dict) -> int:
    """Number of patch versions to keep for a branch."""
    return MAINTAINED_PATCHES if version_config.get('maintained', True) else EOL_PATCHES


def fetch_branch_releases(minor: str, count: int) -> Optional[Dict]:
    """Fetch the most recent `count` releases of a given X.Y branch from php.net."""
    try:
        url = f"https://www.php.net/releases/index.php?json&version={minor}&max={count}"
        with urllib.request.urlopen(url, timeout=15) as response:
            return json.loads(response.read())
    except (URLError, json.JSONDecodeError) as e:
        print(f"Error fetching PHP releases for {minor}: {e}", file=sys.stderr)
        return None


def latest_patches(minor: str, count: int) -> Optional[List[int]]:
    """Return the last `count` patch numbers for a branch, sorted ascending."""
    data = fetch_branch_releases(minor, count)
    if not data:
        return None

    patches = []
    for version_key in data.keys():
        m = re.match(r'^(\d+)\.(\d+)\.(\d+)$', version_key)
        if m and f"{m.group(1)}.{m.group(2)}" == minor:
            patches.append(int(m.group(3)))

    if not patches:
        return None

    return sorted(set(patches), reverse=True)[:count][::-1]


def check_for_updates(config_path: Path) -> tuple[bool, Dict]:
    """Recompute the patch window for every configured PHP branch."""
    with open(config_path, 'r') as f:
        config = json.load(f)

    versions = config['versions']
    updated = False

    for minor, version_config in versions.items():
        count = window_size(version_config)
        patches = latest_patches(minor, count)

        if patches is None:
            print(f"  PHP {minor}: could not fetch releases, keeping current", file=sys.stderr)
            continue

        new_php_version = f"{minor}.{patches[-1]}"
        old_patches = version_config.get('patch_versions', [])
        old_php_version = version_config.get('php_version')

        if patches != old_patches or new_php_version != old_php_version:
            kind = "maintained" if version_config.get('maintained', True) else "EOL"
            print(f"✓ PHP {minor} ({kind}, last {count}): "
                  f"{old_patches} → {patches}, latest {new_php_version}")
            version_config['patch_versions'] = patches
            version_config['php_version'] = new_php_version
            updated = True
        else:
            print(f"  PHP {minor}: {old_php_version} patches {old_patches} (up to date)")

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
