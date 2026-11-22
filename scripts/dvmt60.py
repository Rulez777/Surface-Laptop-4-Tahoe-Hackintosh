#!/usr/bin/env python3
"""Test-machine DVMT 60 MB OpenCore properties for Tiger Lake Iris Xe.

Surface Laptop 4 (Intel i7-1185G7, 8086:9A49) reports GGC 0xFEC1.
The upstream WhateverXe DVMT section prescribes these two Data properties
and -igfxdvmt for BIOS-fixed 60 MB DVMT. This is *not* a general-purpose
GPU configuration and does not replace installing WhateverXe Graphics
inside macOS. Do not publish a personalized EFI or SMBIOS identifiers.
"""
from __future__ import annotations

IGPU_PATH = "PciRoot(0x0)/Pci(0x2,0x0)"
DVMT_ARG = "-igfxdvmt"
PROPERTIES = {
    "framebuffer-patch-enable": bytes.fromhex("01000000"),
    "framebuffer-stolenmem": bytes.fromhex("0000C003"),
}


def is_ready(config: dict) -> bool:
    props = config.get("DeviceProperties", {}).get("Add", {}).get(IGPU_PATH)
    return isinstance(props, dict) and all(
        isinstance(props.get(name), (bytes, bytearray))
        and bytes(props[name]) == expected
        for name, expected in PROPERTIES.items()
    )


def stage(config: dict) -> list[str]:
    """Stage only missing values. Reject conflicting values; preserve others."""
    additions = config["DeviceProperties"]["Add"]
    if IGPU_PATH not in additions:
        additions[IGPU_PATH] = {}
    props = additions[IGPU_PATH]
    if not isinstance(props, dict):
        raise RuntimeError("iGPU DeviceProperties value must be a dictionary")
    for name, expected in PROPERTIES.items():
        if name in props:
            actual = props[name]
            if not isinstance(actual, (bytes, bytearray)) or bytes(actual) != expected:
                raise RuntimeError("Conflicting iGPU property; refusing to overwrite: " + name)
    changes = []
    for name, expected in PROPERTIES.items():
        if name not in props:
            props[name] = expected
            changes.append(name + "=" + expected.hex())
    return changes
