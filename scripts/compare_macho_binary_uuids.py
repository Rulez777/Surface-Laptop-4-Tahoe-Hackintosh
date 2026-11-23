#!/usr/bin/env python3
"""Compare local x86_64 Mach-O kext executable bytes, normalizing LC_UUID only.

Useful for deciding whether *two builds* differ only in linker-generated
Mach-O UUID. Never changes either file. This does not validate or sign
a kext, compare loaded kernel memory, or certify boot compatibility.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
import sys

MAGIC_64 = 0xfeedfacf
CPU_X86_64 = 0x01000007
LC_UUID = 0x1b
MAX_BYTES = 80 * 1024 * 1024


def inspect(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Expected regular Mach-O file")
    size = path.stat().st_size
    if not 32 <= size <= MAX_BYTES:
        raise ValueError("Binary is outside allowed size range")
    raw = path.read_bytes()
    magic, cpu, subcpu, filetype, ncmds, commandsize, flags, reserved = struct.unpack_from(
        "<IiiIIIII", raw, 0)
    if magic != MAGIC_64 or cpu != CPU_X86_64:
        raise ValueError("Expected little-endian x86_64 Mach-O")
    if ncmds < 1 or ncmds > 200 or commandsize > 64*1024 or 32+commandsize > len(raw):
        raise ValueError("Invalid Mach-O load commands")
    cursor = 32
    uuids = []
    for _ in range(ncmds):
        if cursor+8 > 32+commandsize:
            raise ValueError("Invalid Mach-O load command bounds")
        cmd, cmdsize = struct.unpack_from("<II", raw, cursor)
        if cmdsize < 8 or cmdsize % 8 or cursor + cmdsize > 32 + commandsize:
            raise ValueError("Invalid Mach-O load command length")
        if cmd == LC_UUID:
            if cmdsize != 24:
                raise ValueError("Invalid LC_UUID length")
            uuids.append(cursor+8)
        cursor += cmdsize
    if cursor != 32 + commandsize or len(uuids) != 1:
        raise ValueError("Expected exactly one well-formed LC_UUID")
    zeroed = bytearray(raw)
    zeroed[uuids[0]:uuids[0]+16] = b"\x00" * 16
    return {
        "size": len(raw),
        "bytes": raw,
        "uuid_offset": uuids[0],
        "uuid": raw[uuids[0]:uuids[0]+16].hex(),
        "sha256": sha256(raw).hexdigest(),
        "normalized_sha256": sha256(zeroed).hexdigest(),
    }


def compare(first: Path, second: Path) -> dict:
    a = inspect(first)
    b = inspect(second)
    # Do not emit machine paths or binary bytes.
    return {
        "format": "Mach-O x86_64",
        "read_only": True,
        "first_size": a["size"],
        "second_size": b["size"],
        "full_binary_equal": a["sha256"] == b["sha256"],
        "uuid_offsets_equal": a["uuid_offset"] == b["uuid_offset"],
        "uuids_equal": a["uuid"] == b["uuid"],
        "all_non_uuid_bytes_equal": (
            a["normalized_sha256"] == b["normalized_sha256"]),
        "byte_identical_except_uuid": (
            a["sha256"] != b["sha256"]
            and a["normalized_sha256"] == b["normalized_sha256"]),
        "normalized_digest": a["normalized_sha256"]
          if a["normalized_sha256"] == b["normalized_sha256"] else None,
        "warning": (
            "A matching normalized digest establishes file byte identity "
            "except LC_UUID; it does not prove an installed GPU fix or "
            "safe kernel loading."
        ),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("first", type=Path)
    p.add_argument("second", type=Path)
    args = p.parse_args(argv)
    try:
        result = compare(args.first, args.second)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["all_non_uuid_bytes_equal"] else 1
    except (OSError, ValueError, struct.error) as err:
        print("MACHO_COMPARISON_ERROR:", type(err).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
