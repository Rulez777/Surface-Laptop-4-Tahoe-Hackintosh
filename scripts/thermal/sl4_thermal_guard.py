#!/usr/bin/env python3
"""Experimental Surface Laptop 4 Intel thermal guard (not a direct fan RPM driver).

Reads ONLY the SMC TC0D CPU die temperature. Read-only --probe and --monitor
are the default safe paths. --control is explicitly opt-in, and requests
BigSurface TMP profiles, never direct fan speed. TMP=4 may INCREASE CPU heat.
No guarantees about fan RPM, full speed, or physical EC response.

Requires a working SMC CPU die sensor (usually SMCProcessor.kext) and
BigSurface. Never use battery temperature TC0P as a substitute for TC0D.
"""
import argparse
import ctypes as C
import datetime
import os
import subprocess
import sys
import time

BASE, HOT, CRITICAL = 3, 4, 1
HOT_C, COOL_C, CRITICAL_C = 80.0, 72.0, 90.0
MIN_C, MAX_C = 15.0, 105.0
INTERVAL = 5


def say(message):
    print(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {message}", flush=True)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def smc_error(result, key):
    """Decode known SMC status separately from IOKit transport errors."""
    if result == 0x84:
        return f"SMC key {key} not found (0x84); SMCProcessor.kext may be missing or CPU sensor unavailable"
    if result == 0x85:
        return f"SMC key {key} not readable (0x85)"
    return f"SMC key {key} rejected request (0x{result:02X})"


def check_hardware():
    require(sys.platform == "darwin", "Only macOS is supported")
    result = subprocess.run(["/usr/sbin/ioreg", "-p", "IOACPIPlane", "-lw0"],
        capture_output=True, text=True, check=True, timeout=20)
    require("MSHW0250" in result.stdout and "MSHW0084" in result.stdout,
        "Not a supported Surface Laptop 4 Intel MSHW0250")


class Vers(C.Structure):
    _fields_ = [("major", C.c_uint8), ("minor", C.c_uint8), ("build", C.c_uint8),
                ("reserved", C.c_uint8), ("release", C.c_uint16)]


class Limits(C.Structure):
    _fields_ = [("version", C.c_uint16), ("length", C.c_uint16),
                ("cpu", C.c_uint32), ("gpu", C.c_uint32), ("memory", C.c_uint32)]


class KeyInfo(C.Structure):
    _fields_ = [("size", C.c_uint32), ("type", C.c_uint32), ("attrs", C.c_uint8)]


class Data(C.Structure):
    _fields_ = [("key", C.c_uint32), ("vers", Vers), ("limits", Limits),
                ("info", KeyInfo), ("result", C.c_uint8), ("status", C.c_uint8),
                ("command", C.c_uint8), ("data32", C.c_uint32),
                ("payload", C.c_uint8 * 32)]


class CpuDie:
    def __init__(self):
        require(C.sizeof(Data) == 80, "Unexpected AppleSMC ABI")
        self.io = C.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
        libc = C.CDLL("/usr/lib/libSystem.B.dylib")
        self.io.IOServiceMatching.argtypes = [C.c_char_p]
        self.io.IOServiceMatching.restype = C.c_void_p
        self.io.IOServiceGetMatchingService.argtypes = [C.c_uint32, C.c_void_p]
        self.io.IOServiceGetMatchingService.restype = C.c_uint32
        self.io.IOServiceOpen.argtypes = [C.c_uint32, C.c_uint32, C.c_uint32, C.POINTER(C.c_uint32)]
        self.io.IOServiceOpen.restype = C.c_int32
        self.io.IOServiceClose.argtypes = [C.c_uint32]
        self.io.IOServiceClose.restype = C.c_int32
        self.io.IOObjectRelease.argtypes = [C.c_uint32]
        self.io.IOConnectCallStructMethod.argtypes = [C.c_uint32, C.c_uint32, C.c_void_p, C.c_size_t, C.c_void_p, C.POINTER(C.c_size_t)]
        self.io.IOConnectCallStructMethod.restype = C.c_int32
        service = self.io.IOServiceGetMatchingService(0, self.io.IOServiceMatching(b"AppleSMC"))
        require(service != 0, "AppleSMC not present")
        self.conn = C.c_uint32(0)
        try:
            task = C.c_uint32.in_dll(libc, "mach_task_self_").value
            status = self.io.IOServiceOpen(service, task, 0, C.byref(self.conn))
        finally:
            self.io.IOObjectRelease(service)
        require(status == 0, f"AppleSMC open failed: {status:#x}")

    def close(self):
        if self.conn.value:
            self.io.IOServiceClose(self.conn.value)
            self.conn.value = 0

    def call(self, request):
        response = Data()
        size = C.c_size_t(C.sizeof(response))
        rc = self.io.IOConnectCallStructMethod(self.conn.value, 2, C.byref(request),
            C.sizeof(request), C.byref(response), C.byref(size))
        require(rc == 0 and size.value == C.sizeof(response),
                f"AppleSMC IOKit transport failure: rc={rc}, size={size.value}")
        require(response.result == 0,
                smc_error(response.result, "TC0D"))
        require(response.status == 0,
                f"AppleSMC status={response.status}; CPU die temperature is not trustworthy")
        return response

    def read(self):
        request = Data()
        request.key = int.from_bytes(b"TC0D", "big")
        request.command = 9  # SMC_CMD_READ_KEYINFO
        info = self.call(request).info
        require(info.size == 2 and info.type == int.from_bytes(b"sp78", "big"),
                "SMC CPU DIE key TC0D missing or not sp78; refusing temperature control")
        request.info.size = info.size
        request.command = 5  # SMC_CMD_READ_BYTES
        packet = self.call(request)
        temp = int.from_bytes(bytes(packet.payload[:2]), "big", signed=True) / 256.0
        require(MIN_C <= temp <= MAX_C, f"Invalid CPU DIE temperature: {temp:.2f}")
        return temp


class Policy:
    """Pure policy; all transitions include hysteresis, no hardware operations."""
    def __init__(self):
        self.state, self.hot_count, self.cool_since = "balanced", 0, None

    def select(self, temp, now):
        require(MIN_C <= temp <= MAX_C, "Invalid temperature")
        if temp >= CRITICAL_C:
            self.state, self.cool_since = "critical", None
            return CRITICAL
        if self.state == "critical":
            if temp <= COOL_C:
                self.cool_since = now if self.cool_since is None else self.cool_since
                if now - self.cool_since >= 60:
                    self.state, self.cool_since = "balanced", None
                    return BASE
            else:
                self.cool_since = None
            return CRITICAL
        if self.state == "balanced":
            self.hot_count = self.hot_count + 1 if temp >= HOT_C else 0
            if self.hot_count >= 2:
                self.state, self.cool_since = "hot", None
                return HOT
            return BASE
        if self.state == "hot":
            if temp <= COOL_C:
                self.cool_since = now if self.cool_since is None else self.cool_since
                if now - self.cool_since >= 60:
                    self.state, self.cool_since, self.hot_count = "balanced", None, 0
                    return BASE
            else:
                self.cool_since = None
            return HOT
        raise RuntimeError("Invalid policy state")


class BigSurface:
    def __init__(self):
        self.io = C.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
        self.cf = C.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        self.io.IOServiceMatching.argtypes = [C.c_char_p]
        self.io.IOServiceMatching.restype = C.c_void_p
        self.io.IOServiceGetMatchingService.argtypes = [C.c_uint32, C.c_void_p]
        self.io.IOServiceGetMatchingService.restype = C.c_uint32
        self.io.IORegistryEntrySetCFProperties.argtypes = [C.c_uint32, C.c_void_p]
        self.io.IORegistryEntrySetCFProperties.restype = C.c_int32
        self.io.IOObjectRelease.argtypes = [C.c_uint32]
        self.cf.CFStringCreateWithCString.argtypes = [C.c_void_p, C.c_char_p, C.c_uint32]
        self.cf.CFStringCreateWithCString.restype = C.c_void_p
        self.cf.CFNumberCreate.argtypes = [C.c_void_p, C.c_int32, C.c_void_p]
        self.cf.CFNumberCreate.restype = C.c_void_p
        self.cf.CFDictionaryCreateMutable.argtypes = [C.c_void_p, C.c_long, C.c_void_p, C.c_void_p]
        self.cf.CFDictionaryCreateMutable.restype = C.c_void_p
        self.cf.CFDictionarySetValue.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p]
        self.cf.CFRelease.argtypes = [C.c_void_p]

    def set(self, mode):
        require(mode in (1, 3, 4), "Unsupported TMP mode")
        service = self.io.IOServiceGetMatchingService(0, self.io.IOServiceMatching(b"SurfaceBatteryDriver"))
        require(service != 0, "SurfaceBatteryDriver missing")
        key = val = dictionary = 0
        try:
            key = self.cf.CFStringCreateWithCString(None, b"PerformanceMode", 0x08000100)
            sample = C.c_int32(mode)
            val = self.cf.CFNumberCreate(None, 3, C.byref(sample))
            dictionary = self.cf.CFDictionaryCreateMutable(None, 0, None, None)
            require(key and val and dictionary, "Cannot allocate CF objects")
            self.cf.CFDictionarySetValue(dictionary, key, val)
            result = self.io.IORegistryEntrySetCFProperties(service, dictionary)
            require(result == 0, f"IOKit refused TMP request: {result:#x}")
        finally:
            for x in (dictionary, val, key):
                if x:
                    self.cf.CFRelease(x)
            self.io.IOObjectRelease(service)
        # BigSurface code returns 0 even if its internal EC send fails.
        say(f"Requested TMP profile {mode}; neither EC receipt nor fan RPM can be verified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument("--probe", action="store_true", help="Read CPU DIE temperature once; no writes")
    commands.add_argument("--monitor", action="store_true", help="Log decisions, never write TMP")
    commands.add_argument("--control", action="store_true", help="EXPERIMENTAL: request TMP profiles, NOT fan RPM")
    parser.add_argument("--ack", default="", help="Required with --control: I-UNDERSTAND-TMP-IS-NOT-FAN-RPM")
    parser.add_argument("--samples", type=int, default=0, help="0 = continuous, positive = finite")
    args = parser.parse_args()
    require(args.samples >= 0, "Invalid sample count")
    if args.control:
        require(args.ack == "I-UNDERSTAND-TMP-IS-NOT-FAN-RPM", "Explicit --ack required")
        require(os.geteuid() == 0, "--control requires sudo")
    check_hardware()
    sensor = CpuDie()
    try:
        temp = sensor.read()
        say(f"Validated SMC CPU DIE TC0D = {temp:.2f} C (NOT battery temperature)")
        if args.probe:
            return
        controller = BigSurface() if args.control else None
        policy, previous, failures = Policy(), None, 0
        sample = 0
        while args.samples == 0 or sample < args.samples:
            try:
                if sample:
                    temp = sensor.read()
                target = policy.select(temp, time.monotonic())
                failures = 0
                say(f"CPU DIE {temp:.2f} C; state={policy.state}; TMP={target}; writes={'ON' if controller else 'OFF'}")
                if target != previous:
                    if controller:
                        controller.set(target)
                    previous = target
            except (RuntimeError, OSError) as error:
                failures += 1
                say(f"SENSOR/IOKIT ERROR: {error}")
                if failures >= 2 and previous == HOT and controller:
                    controller.set(BASE)
                    previous = BASE
                    say("Sensor failed twice: retreated to TMP mode 3")
                if failures >= 3:
                    raise RuntimeError("Repeated sensor failures, stopping monitor") from error
            sample += 1
            if args.samples == 0 or sample < args.samples:
                time.sleep(INTERVAL)
    finally:
        sensor.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        say("Stopped by user")
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        say(f"STOP: {error}")
        sys.exit(1)
