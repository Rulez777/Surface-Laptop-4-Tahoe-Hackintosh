#!/usr/bin/env python3
"""Read-only VideoToolbox codec/encoder capability audit for Intel Surface.

Important: API advertisement is NOT proof of successful hardware frame decode.
No kext, EFI, CoreMedia, pmset, browser settings, or drivers are changed.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import plistlib
import sys

VT_PATH = "/System/Library/Frameworks/VideoToolbox.framework/VideoToolbox"
CF_PATH = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
CODECS = {"H.264": b"avc1", "HEVC": b"hvc1", "VP9": b"vp09", "AV1": b"av01"}
CAPABILITY_SYMBOLS = {
    "HEVC": "VTCopyHEVCDecoderCapabilitiesDictionary",
    "VP9": "VTCopyVP9DecoderCapabilitiesDictionary",
    "AV1": "VTCopyAV1DecoderCapabilitiesDictionary",
}


def codec_name(codec_type):
    """FourCC for a VideoToolbox CodecType integer (or None if invalid)."""
    if not isinstance(codec_type, int) or not 0 <= codec_type < 2**32:
        return None
    raw = codec_type.to_bytes(4, "big")
    return raw.decode("ascii") if all(32 <= char <= 126 for char in raw) else None


def summarize_encoders(encoders):
    """Hardware-registered vs software encoders, no guessed capabilities."""
    useful = {code.decode("ascii"): name for name, code in CODECS.items()}
    registered = []
    for encoder in encoders:
        fourcc = codec_name(encoder.get("CodecType"))
        if fourcc not in useful:
            continue
        registered.append({
            "codec": useful[fourcc],
            "fourcc": fourcc,
            "name": str(encoder.get("EncoderName", "")),
            "hardware_advertised": bool(encoder.get("IsHardwareAccelerated", False)),
        })
    hardware = {
        name: any(e["codec"] == name and e["hardware_advertised"] for e in registered)
        for name in CODECS
    }
    return registered, hardware


class CoreFoundationPropertyLists:
    """Convert retained CF property-list references to built-in Python data."""

    def __init__(self):
        self.cf = ctypes.CDLL(CF_PATH)
        self.cf.CFPropertyListCreateData.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
            ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p),
        ]
        self.cf.CFPropertyListCreateData.restype = ctypes.c_void_p
        self.cf.CFDataGetLength.argtypes = [ctypes.c_void_p]
        self.cf.CFDataGetLength.restype = ctypes.c_long
        self.cf.CFDataGetBytePtr.argtypes = [ctypes.c_void_p]
        self.cf.CFDataGetBytePtr.restype = ctypes.c_void_p
        self.cf.CFRelease.argtypes = [ctypes.c_void_p]

    def convert_and_release(self, owned_ref):
        if not owned_ref:
            return None
        data = None
        error = ctypes.c_void_p()
        try:
            # kCFPropertyListXMLFormat_v1_0 = 100
            data = self.cf.CFPropertyListCreateData(None, owned_ref, 100, 0, ctypes.byref(error))
            if not data:
                raise RuntimeError("VideoToolbox returned a non-serializable property list")
            raw = ctypes.string_at(self.cf.CFDataGetBytePtr(data),
                                   self.cf.CFDataGetLength(data))
            return plistlib.loads(raw)
        finally:
            if data:
                self.cf.CFRelease(data)
            if error.value:
                self.cf.CFRelease(error)
            self.cf.CFRelease(owned_ref)


def survey(vt, cf):
    probe = vt.VTIsHardwareDecodeSupported
    probe.argtypes = [ctypes.c_uint32]
    probe.restype = ctypes.c_bool
    decoders = {
        name: bool(probe(int.from_bytes(fourcc, "big")))
        for name, fourcc in CODECS.items()
    }
    capability_dicts = {}
    for name, symbol in CAPABILITY_SYMBOLS.items():
        function = getattr(vt, symbol, None)
        if function is None:
            capability_dicts[name] = {"api_present": False, "dictionary": None}
            continue
        function.argtypes = []
        function.restype = ctypes.c_void_p
        result = cf.convert_and_release(function())
        capability_dicts[name] = {"api_present": True, "dictionary": result}

    copy_encoders = vt.VTCopyVideoEncoderList
    copy_encoders.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    copy_encoders.restype = ctypes.c_int
    ref = ctypes.c_void_p()
    status = copy_encoders(None, ctypes.byref(ref))
    if status:
        if ref.value:
            cf.cf.CFRelease(ref)
        raise RuntimeError(f"VTCopyVideoEncoderList failed with OSStatus {status}")
    encoders = cf.convert_and_release(ref)
    registry, hw_encoders = summarize_encoders(encoders or [])
    return {
        "video_hardware_decoders_advertised": decoders,
        "video_decoder_capability_dictionaries": capability_dicts,
        "video_encoder_registry": registry,
        "video_hardware_encoders_advertised": hw_encoders,
        "interpretation": (
            "Advertisement/registration only; actual hardware decode must be "
            "verified with a real stream and decoder/GPU evidence. A null "
            "capability dictionary is not proof that Intel silicon lacks the codec."
        ),
        "changes_to_system": "none",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Output JSON report.")
    args = parser.parse_args(argv)
    if sys.platform != "darwin":
        parser.error("This audit must run on installed macOS, not Windows or Linux.")
    report = survey(ctypes.CDLL(VT_PATH), CoreFoundationPropertyLists())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Surface macOS VideoToolbox — read-only codec audit")
        for name, advertised in report["video_hardware_decoders_advertised"].items():
            has_caps = report["video_decoder_capability_dictionaries"].get(name, {})
            print(f"  {name}: hardware decoder advertised={advertised}; "
                  f"capabilities returned={has_caps.get('dictionary') is not None}")
        for name, advertised in report["video_hardware_encoders_advertised"].items():
            print(f"  {name}: hardware encoder advertised={advertised}")
        print("NOTE:", report["interpretation"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
