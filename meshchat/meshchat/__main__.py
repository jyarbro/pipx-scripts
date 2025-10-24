#!/usr/bin/env python3

import os
import sys
import json
import subprocess
import requests
from pathlib import Path


REPO_OWNER = "liamcottle"
REPO_NAME = "reticulum-meshchat"
APP_NAME = "meshchat"
CONFIG_DIR = Path.home() / ".config" / APP_NAME
IMAGES_DIR = CONFIG_DIR / "images"
VERSION_FILE = CONFIG_DIR / "current_version.json"


def ensure_dirs():
    """Create necessary directories"""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def get_current_version():
    """Read current installed version from file"""
    if not VERSION_FILE.exists():
        return None
    try:
        with open(VERSION_FILE, 'r') as f:
            data = json.load(f)
            return data.get('version')
    except Exception as e:
        print(f"⚠️  Error reading version file: {e}")
        return None


def save_current_version(version, appimage_path):
    """Save current version to file"""
    try:
        with open(VERSION_FILE, 'w') as f:
            json.dump({
                'version': version,
                'appimage_path': str(appimage_path)
            }, f, indent=2)
    except Exception as e:
        print(f"⚠️  Error saving version file: {e}")


def get_latest_release():
    """Fetch latest release info from GitHub API"""
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract version and AppImage URL
        tag_name = data.get('tag_name', '')
        version = tag_name.lstrip('v')

        # Find the AppImage asset
        appimage_url = None
        for asset in data.get('assets', []):
            if asset.get('name', '').endswith('.AppImage'):
                appimage_url = asset.get('browser_download_url')
                break

        if not appimage_url:
            print("❌ No AppImage found in latest release")
            return None

        return {
            'version': version,
            'tag_name': tag_name,
            'url': appimage_url,
            'filename': os.path.basename(appimage_url)
        }
    except requests.RequestException as e:
        print(f"❌ Error fetching release info: {e}")
        return None


def download_appimage(url, dest_path):
    """Download AppImage file"""
    print(f"📥 Downloading {url}...")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r  Progress: {percent:.1f}%", end='', flush=True)

        print()  # New line after progress
        print(f"✅ Downloaded to {dest_path}")

        # Make executable
        os.chmod(dest_path, 0o755)
        return True
    except Exception as e:
        print(f"❌ Error downloading: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def run_appimage(appimage_path):
    """Execute the AppImage detached from terminal"""
    if not appimage_path.exists():
        print(f"❌ AppImage not found: {appimage_path}")
        return False

    try:
        # Run the AppImage detached from the terminal
        # Using Popen with subprocess.DEVNULL to disconnect from terminal
        args = sys.argv[1:]
        subprocess.Popen(
            [str(appimage_path)] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True
        )
        return True
    except Exception as e:
        print(f"❌ Error running AppImage: {e}")
        return False


def version_compare(v1, v2):
    """Compare two version strings (e.g., '2.2.1' vs '2.2.0')"""
    try:
        parts1 = [int(x) for x in v1.split('.')]
        parts2 = [int(x) for x in v2.split('.')]

        # Pad to same length
        max_len = max(len(parts1), len(parts2))
        parts1 += [0] * (max_len - len(parts1))
        parts2 += [0] * (max_len - len(parts2))

        # Compare
        for p1, p2 in zip(parts1, parts2):
            if p1 > p2:
                return 1
            elif p1 < p2:
                return -1
        return 0
    except Exception:
        # If comparison fails, assume different
        return -1 if v1 != v2 else 0


def main():
    ensure_dirs()

    # Get current version
    current_version = get_current_version()
    if current_version:
        print(f"📦 Current version: {current_version}")
    else:
        print("📦 No version installed")

    # Check for latest release
    print("🔍 Checking for latest release...")
    latest = get_latest_release()

    if not latest:
        print("❌ Could not fetch release information")
        # Try to run existing version if available
        if current_version:
            version_data_path = VERSION_FILE
            if version_data_path.exists():
                try:
                    with open(version_data_path, 'r') as f:
                        data = json.load(f)
                        appimage_path = Path(data.get('appimage_path', ''))
                        if appimage_path.exists():
                            print("⚠️  Running existing version...")
                            run_appimage(appimage_path)
                        else:
                            print("❌ Existing AppImage not found")
                except Exception:
                    pass
        sys.exit(1)

    latest_version = latest['version']
    print(f"🌐 Latest version: {latest_version}")

    # Determine if we need to download
    needs_download = False
    if not current_version:
        print("📥 First-time installation")
        needs_download = True
    elif version_compare(latest_version, current_version) > 0:
        print(f"⬆️  Newer version available: {current_version} -> {latest_version}")
        needs_download = True
    else:
        print("✅ Already up to date")

    # Download if needed
    appimage_path = IMAGES_DIR / latest['filename']
    if needs_download:
        if not download_appimage(latest['url'], appimage_path):
            print("❌ Download failed")
            sys.exit(1)
        save_current_version(latest_version, appimage_path)

    # Run the AppImage
    print(f"🚀 Launching {APP_NAME}...")
    run_appimage(appimage_path)


if __name__ == "__main__":
    main()
