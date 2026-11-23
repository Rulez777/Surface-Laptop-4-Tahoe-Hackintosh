#!/usr/bin/env python3
"""Optional notarized IINA 1.5.1 local AV1/VP9 player for installed macOS.

All-in-one recovery companion. Never edits VideoToolbox registration, drivers,
EFI, NVRAM, user default app associations or Safari. A *software* decoder
fallback for local AV1 MP4 and VP9 WebM files; no GPU-media-block claim.

--check is read-only. --install downloads a SHA-256 pinned official release.
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

VERSION = "1.5.1"
APP_NAME = "IINA.app"
BUNDLE_ID = "com.colliderli.iina"
TEAM = "67CQ77V27R"
PUBLISHER = f"Developer ID Application: Hechen Li ({TEAM})"
DOWNLOAD = "https://github.com/iina/iina/releases/download/v1.5.1/IINA.v1.5.1.dmg"
DOWNLOAD_SHA256 = "f414507ec60bcfeda3a9f539f74470253e31b619d031e7a9e9a71519da1598cd"
DOWNLOAD_SIZE = 113092405
MAX_DMG_BYTES = 220 * 1024 * 1024


def run(*argv, timeout=180):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                            check=False)
    if result.returncode:
        raise RuntimeError(f"{argv[0]} failed ({result.returncode}): "
                           f"{(result.stderr + result.stdout).strip()[-700:]}")
    return result.stdout + result.stderr


def app_path():
    return Path.home() / "Applications" / APP_NAME


def verify_app(app):
    """Reject tampered/not-notarized/injected applications before accepting."""
    app = Path(app)
    if app.is_symlink() or not app.is_dir():
        raise RuntimeError("IINA app must be an ordinary directory, not a symlink")
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    if info.get("CFBundleIdentifier") != BUNDLE_ID:
        raise RuntimeError("IINA bundle identifier mismatch")
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", str(app), timeout=150)
    identity = run("/usr/bin/codesign", "-dv", "--verbose=4", str(app))
    if any(field not in identity for field in (
            f"Identifier={BUNDLE_ID}", f"TeamIdentifier={TEAM}",
            f"Authority={PUBLISHER}")):
        raise RuntimeError("IINA publisher identity mismatch")
    notarization = run("/usr/sbin/spctl", "--assess", "--type",
                       "execute", "-vv", str(app), timeout=160)
    if "source=Notarized Developer ID" not in notarization:
        raise RuntimeError("IINA not accepted as notarized by Gatekeeper")
    library = app / "Contents/Frameworks/libmpv.2.dylib"
    if not library.is_file() or library.is_symlink():
        raise RuntimeError("Signed IINA app lacks libmpv runtime")
    return {"version": info.get("CFBundleShortVersionString"),
            "bundle": BUNDLE_ID, "team": TEAM,
            "signed_and_notarized": True,
            "path": str(app)}


def check():
    app = app_path()
    if not app.exists() and not app.is_symlink():
        return {"installed": False, "path": str(app),
                "intel_av1_vp9_hardware_unlocked": False}
    return {"installed": True, "app": verify_app(app),
            "intel_av1_vp9_hardware_unlocked": False,
            "media": "local AV1/VP9 file software playback; hardware decode not enabled"}


def url_allowed(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    return (parsed.hostname or "").lower() in {
        "github.com", "release-assets.githubusercontent.com"
    }


def download_pinned(path):
    """Pin final bytes as well as transport URL to avoid moving release alias."""
    if not url_allowed(DOWNLOAD):
        raise RuntimeError("IINA download URL rejected")
    digest = hashlib.sha256()
    total = 0
    req = urllib.request.Request(
        DOWNLOAD, headers={"User-Agent": "SL4-Tahoe-Local-IINA/1.0"})
    with urllib.request.urlopen(req, timeout=90) as response:
        if not url_allowed(response.geturl()):
            raise RuntimeError("IINA release redirected to unexpected host")
        with path.open("xb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DMG_BYTES:
                    raise RuntimeError("IINA download exceeds size limit")
                out.write(chunk)
                digest.update(chunk)
    if total != DOWNLOAD_SIZE or digest.hexdigest() != DOWNLOAD_SHA256:
        raise RuntimeError("IINA official v1.5.1 release SHA-256/size mismatch")
    return digest.hexdigest()


def install():
    if sys.platform != "darwin":
        raise RuntimeError("macOS is required")
    target = app_path()
    if target.exists() or target.is_symlink():
        # Do not overwrite an existing app, including a different verified version.
        report = check()
        print("IINA_EXISTING_VERIFIED", json.dumps(report, sort_keys=True))
        return report
    target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    parent = Path.home() / "Downloads"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sl4-iina-", dir=str(parent)) as work:
        temp = Path(work)
        dmg = temp / "IINA.dmg"
        digest = download_pinned(dmg)
        run("/usr/bin/hdiutil", "verify", str(dmg), timeout=90)
        mount = temp / "mounted"
        mount.mkdir()
        mounted = False
        try:
            run("/usr/bin/hdiutil", "attach", "-readonly", "-nobrowse",
                "-quiet", "-mountpoint", str(mount), str(dmg), timeout=60)
            mounted = True
            source = mount / APP_NAME
            metadata = verify_app(source)
            if metadata["version"] != VERSION:
                raise RuntimeError("IINA app version differs from pinned release")
            staged_parent = Path(tempfile.mkdtemp(
                prefix=".sl4-iina-", dir=str(target.parent)))
            try:
                staged = staged_parent / APP_NAME
                run("/usr/bin/ditto", str(source), str(staged), timeout=240)
                verify_app(staged)
                if target.exists() or target.is_symlink():
                    raise RuntimeError("IINA appeared during staging; no overwrite")
                os.rename(staged, target)  # atomic within ~/Applications
            finally:
                shutil.rmtree(staged_parent, ignore_errors=True)
        finally:
            if mounted:
                run("/usr/bin/hdiutil", "detach", "-quiet", str(mount), timeout=90)
    report = check()
    report["release_dmg_sha256"] = digest
    print("IINA_AV1_VP9_SOFTWARE_PLAYBACK_READY",
          json.dumps(report, sort_keys=True))
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Read-only")
    mode.add_argument("--install", action="store_true", help="Opt-in IINA install")
    args = p.parse_args(argv)
    if sys.platform != "darwin":
        p.error("This helper runs only on installed macOS")
    print(json.dumps(check() if args.check else install(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print("SL4_IINA_ERROR:", exc, file=sys.stderr)
        sys.exit(2)
