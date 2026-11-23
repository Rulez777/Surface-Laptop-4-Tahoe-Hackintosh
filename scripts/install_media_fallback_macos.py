#!/usr/bin/env python3
"""Optional AV1/VP9 web playback fallback for installed macOS Tahoe.

Installs a verified, notarized official Mozilla Firefox to ~/Applications.
This allows software AV1/VP9 playback without touching working GPU kexts.
It does NOT unlock Intel video-engine decoding, register VideoToolbox codecs,
change Safari/default apps, install LaunchAgents, or need administrator access.

The installer is opt-in: --check never changes anything; --install is explicit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

DOWNLOAD = "https://download.mozilla.org/?product=firefox-latest&os=osx&lang=en-US"
TEAM = "43AQ936H96"
BUNDLE_ID = "org.mozilla.firefox"
MAX_DMG_BYTES = 400 * 1024 * 1024
APP_NAME = "Firefox.app"


def run(*argv, timeout=180):
    r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    if r.returncode:
        raise RuntimeError(
            f"{argv[0]} failed ({r.returncode}): {((r.stderr or '') + ' ' + (r.stdout or '')).strip()[-700:]}"
        )
    return r.stdout + r.stderr


def verify_publisher_signature(app):
    """Verify both sealed app signature AND official Apple-notarized publisher."""
    app = Path(app)
    if not app.is_dir() or app.is_symlink():
        raise RuntimeError("Firefox must be a real app directory, not a symlink")
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    if info.get("CFBundleIdentifier") != BUNDLE_ID:
        raise RuntimeError("Unexpected app bundle identifier")
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", str(app))
    identity = run("/usr/bin/codesign", "-dv", "--verbose=4", str(app))
    if (f"TeamIdentifier={TEAM}" not in identity
            or f"Identifier={BUNDLE_ID}" not in identity
            or f"Authority=Developer ID Application: Mozilla Corporation ({TEAM})" not in identity):
        raise RuntimeError("Publisher signature does not match Mozilla Corporation")
    gatekeeper = run("/usr/sbin/spctl", "--assess", "--type", "execute", "-vv", str(app), timeout=160)
    if "source=Notarized Developer ID" not in gatekeeper:
        raise RuntimeError("Firefox was not accepted as notarized by Gatekeeper")
    return {
        "bundle": BUNDLE_ID,
        "team": TEAM,
        "version": info.get("CFBundleShortVersionString"),
        "location": str(app),
        "signed_and_notarized": True,
    }


def target_path():
    return Path.home() / "Applications" / APP_NAME


def status():
    app = target_path()
    if not app.exists() and not app.is_symlink():
        return {"installed": False, "path": str(app), "gpu_av1_vp9_unlocked": False}
    verified = verify_publisher_signature(app)
    return {"installed": True, "app": verified, "gpu_av1_vp9_unlocked": False,
            "video_support": "AV1/VP9 SOFTWARE fallback in Firefox; no VideoToolbox change"}


def trusted_download(url):
    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and
            (hostname == "download.mozilla.org" or
             hostname == "mozilla.net" or hostname.endswith(".mozilla.net")))


def download_official(path):
    if not trusted_download(DOWNLOAD):
        raise RuntimeError("Invalid Mozilla download URL")
    request = urllib.request.Request(DOWNLOAD, headers={"User-Agent": "SL4-Media-Fallback/1.0"})
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(request, timeout=90) as response:
        if not trusted_download(response.geturl()):
            raise RuntimeError("Download redirected outside official Mozilla domains")
        with path.open("xb") as destination:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DMG_BYTES:
                    raise RuntimeError("Official browser download exceeded safe size limit")
                destination.write(chunk)
                digest.update(chunk)
    if total < 25 * 1024 * 1024:
        raise RuntimeError("Unexpectedly small Firefox disk image")
    return {"sha256": digest.hexdigest(), "size": total,
            "resolved_url": response.geturl()}


def install():
    if sys.platform != "darwin":
        raise RuntimeError("Run only in macOS on your Surface")
    destination = target_path()
    if destination.exists() or destination.is_symlink():
        result = status()  # Refuse to overwrite a different or untrusted app.
        print("VERIFIED_EXISTING_FIREFOX", json.dumps(result, sort_keys=True))
        return result

    destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    tmp_root = Path.home() / "Downloads"
    tmp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sl4-firefox-", dir=str(tmp_root)) as working:
        temp = Path(working)
        dmg = temp / "Firefox.dmg"
        download = download_official(dmg)
        run("/usr/bin/hdiutil", "verify", str(dmg), timeout=90)
        mounted = temp / "mounted"
        mounted.mkdir()
        attached = False
        try:
            run("/usr/bin/hdiutil", "attach", "-quiet", "-readonly",
                "-nobrowse", "-mountpoint", str(mounted), str(dmg), timeout=60)
            attached = True
            source = mounted / APP_NAME
            verify_publisher_signature(source)
            staging_parent = Path(tempfile.mkdtemp(
                prefix=".sl4-video-", dir=str(destination.parent)
            ))
            try:
                staged = staging_parent / APP_NAME
                run("/usr/bin/ditto", str(source), str(staged), timeout=240)
                verify_publisher_signature(staged)
                if destination.exists() or destination.is_symlink():
                    raise RuntimeError("Firefox appeared during staging; refusing overwrite")
                os.rename(staged, destination)  # same filesystem, atomic
            finally:
                shutil.rmtree(staging_parent, ignore_errors=True)
        finally:
            if attached:
                run("/usr/bin/hdiutil", "detach", "-quiet", str(mounted), timeout=90)
        result = status()
        result["download_sha256"] = download["sha256"]
        print("FIREFOX_AV1_VP9_SOFTWARE_FALLBACK_INSTALLED")
        print(json.dumps(result, sort_keys=True, indent=2))
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Read-only publisher/installation check")
    group.add_argument("--install", action="store_true", help="Opt-in install of notarized Firefox")
    p.add_argument("--json", action="store_true", help="Machine-readable check")
    a = p.parse_args()
    if sys.platform != "darwin":
        p.error("macOS is required")
    result = status() if a.check else install()
    if a.check:
        if a.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("FIREFOX_FALLBACK_STATUS", json.dumps(result, sort_keys=True))
    return 0 if result["installed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as error:
        print("SL4_MEDIA_FALLBACK_ERROR:", error, file=sys.stderr)
        sys.exit(2)
