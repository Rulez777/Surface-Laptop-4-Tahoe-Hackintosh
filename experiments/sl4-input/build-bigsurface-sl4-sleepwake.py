#!/usr/bin/env python3
"""Reproducible production Surface Laptop 4 input + lid/SAM wake driver build.

Builds five GPL kernel extensions from pinned upstream commits. Never writes to EFI.
The F11 watchdog is functional recovery logic; temporary diagnostic probes are excluded.
"""
from pathlib import Path
import importlib.util
import os
import plistlib
import sys
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
BUILDER_PATH = HERE / "build-bigsurface-sl4.py"
WORK = Path(os.environ.get(
    "BSWORK",
    Path.home() / "Downloads" / "bigsurface-sl4-sleepwake-20261125"
))
if WORK.exists() and "--no-fetch" not in sys.argv:
    raise SystemExit(
        f"Refusing to let the upstream builder delete an existing work directory: {WORK}\n"
        "Set BSWORK to a new, empty path and retry."
    )
if "--no-fetch" in sys.argv and not WORK.exists():
    raise SystemExit(f"--no-fetch requested but work directory does not exist: {WORK}")
os.environ["BSWORK"] = str(WORK)

spec = importlib.util.spec_from_file_location("bigsurface_sl4_builder", BUILDER_PATH)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text()
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one patch anchor, found {count}: {old[:100]!r}")
    path.write_text(source.replace(old, new, 1))


base_patch = builder.patch


def patch_sam_wake() -> None:
    # First apply the existing, already-tested SL4 UART and Tiger Lake-LP port.
    base_patch()

    gpio = builder.SRC / "Dependencies/VoodooGPIO/VoodooGPIO"
    gpio_h = gpio / "VoodooGPIO.hpp"
    gpio_cpp = gpio / "VoodooGPIO.cpp"
    tgl_h = gpio / "TigerLake-LP/VoodooGPIOTigerLakeLP.hpp"

    replace_once(gpio_cpp, '#include "VoodooGPIO.hpp"\n', '#include "VoodooGPIO.hpp"\n#include <libkern/c++/OSBoolean.h>\n')

    # Intel GPIO community registers used by Linux's intel_gpio_irq_wake():
    # GPI_GPE_STS=0x140, GPI_GPE_EN=0x160. The SL4 SAM pin is GPIO 0x12A.
    replace_once(
        gpio_h,
        "    unsigned ie_offset;\n    unsigned pin_base;",
        "    unsigned ie_offset;\n"
        "    unsigned gpe_sts_offset;\n"
        "    unsigned gpe_en_offset;\n"
        "    unsigned pin_base;"
    )
    replace_once(
        gpio_h,
        "    bool controllerIsAwake;\n",
        "    bool controllerIsAwake;\n"
        "    UInt32 wake_gpio_pin {0};\n"
        "    bool wake_gpio_armed {false};\n"
    )
    replace_once(
        gpio_h,
        "    void intel_gpio_irq_mask_unmask(unsigned pin, bool mask);\n",
        "    void intel_gpio_irq_mask_unmask(unsigned pin, bool mask);\n"
        "    IOReturn setWakeForHardwarePin(unsigned pin, bool enabled);\n"
    )
    replace_once(
        gpio_h,
        "    IOReturn setInterruptTypeForPin(int pin, int type);\n",
        "    IOReturn setInterruptTypeForPin(int pin, int type);\n"
        "    IOReturn setWakeForPin(int pin, bool enabled);\n"
    )

    replace_once(
        tgl_h,
        "#define TGL_LP_GPI_IE        0x120\n",
        "#define TGL_LP_GPI_IE        0x120\n"
        "#define TGL_LP_GPI_GPE_STS  0x140\n"
        "#define TGL_LP_GPI_GPE_EN   0x160\n"
    )
    replace_once(
        tgl_h,
        "        .ie_offset = TGL_LP_GPI_IE,                \\\n",
        "        .ie_offset = TGL_LP_GPI_IE,                \\\n"
        "        .gpe_sts_offset = TGL_LP_GPI_GPE_STS,     \\\n"
        "        .gpe_en_offset = TGL_LP_GPI_GPE_EN,       \\\n"
    )

    # Implement the per-pad GPE wake enable exactly as the Intel GPIO Linux
    # driver does: clear stale GPE status, then set/clear the pad's GPE_EN bit.
    old_method = """IOReturn VoodooGPIO::setInterruptTypeForPin(int pin, int type) {
    struct intel_community *community;
    SInt32 hw_pin = intel_gpio_to_pin(pin, &community, nullptr);
    if (hw_pin < 0)
        return kIOReturnNoInterrupt;

    unsigned communityidx = hw_pin - community->pin_base;
    community->interruptTypes[communityidx] = type;
    if (type & IRQ_TYPE_LEVEL_MASK)
        *community->isActiveCommunity = true;
    return kIOReturnSuccess;
}
"""
    new_methods = old_method + """
IOReturn VoodooGPIO::setWakeForHardwarePin(unsigned pin, bool enabled) {
    struct intel_community *community = intel_get_community(pin);
    if (!community || !community->regs ||
        !community->gpe_sts_offset || !community->gpe_en_offset)
        return kIOReturnUnsupported;

    struct intel_padgroup *padgrp = intel_community_get_padgroup(community, pin);
    if (!padgrp)
        return kIOReturnNoInterrupt;

    unsigned gpp_offset = padgroup_offset(padgrp, pin);
    if (gpp_offset >= 32)
        return kIOReturnBadArgument;

    UInt32 bit = static_cast<UInt32>(1U << gpp_offset);
    UInt32 status_offset = community->gpe_sts_offset + padgrp->reg_num * 4;
    UInt32 enable_offset = community->gpe_en_offset + padgrp->reg_num * 4;
    IOVirtualAddress status_reg = community->regs + status_offset;
    IOVirtualAddress enable_reg = community->regs + enable_offset;

    // GPI_GPE_STS is write-one-to-clear.
    writel(bit, status_reg);

    UInt32 value = readl(enable_reg);
    if (enabled)
        value |= bit;
    else
        value &= ~bit;
    writel(value, enable_reg);
    IOLog("%s::SAM GPIO wake %s: HW pin %u GPE_STS=0x%03x GPE_EN=0x%03x bit=%u\\n",
          getName(), enabled ? "armed" : "disarmed", pin,
          status_offset, enable_offset, gpp_offset);

    return kIOReturnSuccess;
}

IOReturn VoodooGPIO::setWakeForPin(int pin, bool enabled) {
    SInt32 hw_pin = intel_gpio_to_pin(static_cast<UInt32>(pin), nullptr, nullptr);
    if (hw_pin < 0)
        return kIOReturnNoInterrupt;

    if (enabled && wake_gpio_armed && wake_gpio_pin != static_cast<UInt32>(pin))
        return kIOReturnBusy;

    if (!enabled && (!wake_gpio_armed || wake_gpio_pin != static_cast<UInt32>(pin)))
        return kIOReturnSuccess;

    IOReturn status = setWakeForHardwarePin(static_cast<unsigned>(hw_pin), enabled);
    if (status != kIOReturnSuccess)
        return status;

    if (enabled) {
        wake_gpio_pin = static_cast<UInt32>(pin);
        wake_gpio_armed = true;
        OSNumber *pin_number = OSNumber::withNumber(wake_gpio_pin, 32);
        if (pin_number) {
            setProperty("SL4SAMWakeGPIO", pin_number);
            pin_number->release();
        }
        setProperty("SL4SAMWakeArmed", kOSBooleanTrue);
        IOLog("%s::Armed SAM wake GPIO 0x%03x (HW pin %u)\\n",
              getName(), wake_gpio_pin, static_cast<unsigned>(hw_pin));
    } else {
        IOLog("%s::Disarmed SAM wake GPIO 0x%03x\\n", getName(), wake_gpio_pin);
        wake_gpio_pin = 0;
        wake_gpio_armed = false;
        setProperty("SL4SAMWakeArmed", kOSBooleanFalse);
    }

    return kIOReturnSuccess;
}
"""
    replace_once(gpio_cpp, old_method, new_methods)

    # The GPE_EN bit must not remain enabled after any resume (including an
    # unrelated USB/RTC wake). The GPIO driver owns the register, so it clears
    # its remembered wake pin after restoring the controller context.
    resume_anchor = """        }
    }
}

bool VoodooGPIO::init(OSDictionary* properties) {
"""
    resume_replacement = """        }
    }

    if (wake_gpio_armed) {
        UInt32 pin = wake_gpio_pin;
        IOReturn wake_status = setWakeForPin(static_cast<int>(pin), false);
        if (wake_status != kIOReturnSuccess)
            IOLog("%s::Failed to disarm SAM wake GPIO 0x%03x after resume: 0x%x\\n",
                  getName(), pin, wake_status);
    }
}

bool VoodooGPIO::init(OSDictionary* properties) {
"""
    replace_once(gpio_cpp, resume_anchor, resume_replacement)

    # Arm only after SAM has received DISPLAY_OFF and D0_EXIT. Guard the
    # exact firmware GPIO so this patch cannot arm an unrelated pin.
    serial_cpp = builder.SRC / "BigSurface/BigSurface/SurfaceSerialHub/SurfaceSerialHubDriver.cpp"
    replace_once(serial_cpp, '#include "SurfaceSerialHubDriver.hpp"\n', '#include "SurfaceSerialHubDriver.hpp"\n#include <libkern/c++/OSBoolean.h>\n')
    sleep_anchor = """            if (getResponse(SSH_TC_SAM, SSH_TID_PRIMARY, 0, SSH_CID_SAM_D0_EXIT, nullptr, 0, true, &ret, 1) != kIOReturnSuccess || ret != 0)
                DBG_LOG("Unexpected response from d0-exit notification");
            uart_interrupt->disable();
"""
    sleep_replacement = """            if (getResponse(SSH_TC_SAM, SSH_TID_PRIMARY, 0, SSH_CID_SAM_D0_EXIT, nullptr, 0, true, &ret, 1) != kIOReturnSuccess || ret != 0)
                DBG_LOG("Unexpected response from d0-exit notification");

            if (getProperty("SL4SAMWakeEnabled") == kOSBooleanTrue) {
                if (gpio_controller && gpio_pin == 0x012A && gpio_irq == 0x00000001) {
                    IOReturn wake_status = gpio_controller->setWakeForPin(gpio_pin, true);
                    if (wake_status != kIOReturnSuccess)
                        LOG("Failed to arm SAM wake GPIO 0x%03x: 0x%x", gpio_pin, wake_status);
                    else
                        LOG("Armed SAM wake GPIO 0x%03x for built-in keyboard/trackpad", gpio_pin);
                } else {
                    LOG("SAM wake not armed: expected GPIO 0x012A edge-rising, got GPIO 0x%03x irq 0x%08x",
                        gpio_pin, gpio_irq);
                }
            }

            uart_interrupt->disable();
"""
    replace_once(serial_cpp, sleep_anchor, sleep_replacement)

    replace_once(
        serial_cpp,
        'void SurfaceSerialHubDriver::gpioWakeUp(IOInterruptEventSource *sender, int count) {\n'
        '    LOG("GPIO wake up event happened!");\n'
        '}\n',
        'void SurfaceSerialHubDriver::gpioWakeUp(IOInterruptEventSource *sender, int count) {\n'
        '    LOG("SAM wake GPIO event on pin 0x%03x (count=%d)", gpio_pin, count);\n'
        '}\n'
    )

    # Opt-in is scoped to the Surface Serial Hub personality, not global.
    info = builder.SRC / "BigSurface/BigSurface/Info.plist"
    plist = plistlib.loads(info.read_bytes())
    personality = plist["IOKitPersonalities"]["Surface Serial Hub"]
    personality["SL4SAMWakeEnabled"] = True
    info.write_bytes(plistlib.dumps(plist, fmt=plistlib.FMT_XML, sort_keys=True))


sam_wake_patch = patch_sam_wake

def patch_production_sleepwake() -> None:
    # Apply the pinned UART/TGL-LP port and the Surface SAM keyboard/trackpad wake path.
    sam_wake_patch()
    patch_root = HERE / "patches"
    expected = json.loads((patch_root / "base-source-hashes.json").read_text())
    for relative, digest in expected.items():
        source = builder.SRC / relative
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual != digest:
            raise RuntimeError(f"Unexpected post-SAM base source for {relative}: {actual}")
    patch_file = patch_root / "sl4-sleepwake-production.patch"
    result = subprocess.run(
        ["/usr/bin/patch", "-p0"], cwd=builder.SRC,
        input=patch_file.read_bytes(), capture_output=True
    )
    if result.returncode:
        raise RuntimeError((result.stdout + result.stderr).decode(errors="replace"))
    print("Applied diagnostic-free SL4 F11 lid GPE watchdog patch.", flush=True)

builder.patch = patch_production_sleepwake

# Bump only the two changed kexts so the installed build is distinguishable.
base_kexts = builder.kexts
def kexts_with_sam_wake_version():
    result = []
    for name, ident, version, srcdir, includes in base_kexts():
        if name == "VoodooGPIO":
            version = "1.2.5"
        elif name == "BigSurface":
            version = "1.2.1"
        result.append((name, ident, version, srcdir, includes))
    return result

builder.kexts = kexts_with_sam_wake_version

print("Building production Surface Laptop 4 sleep/wake kexts in:", WORK, flush=True)
print("Pinned BigSurface:", builder.PINS["BigSurface"][1], flush=True)
print("Pinned VoodooGPIO pin tables:", builder.PINS["VoodooGPIO-upstream"][1], flush=True)
builder.main()

if "--check" not in sys.argv:
    gpio_info = plistlib.loads((builder.OUT / "VoodooGPIO.kext/Contents/Info.plist").read_bytes())
    big_info = plistlib.loads((builder.OUT / "BigSurface.kext/Contents/Info.plist").read_bytes())
    assert gpio_info.get("CFBundleVersion") == "1.2.5"
    assert big_info.get("CFBundleVersion") == "1.2.1"
    assert big_info["IOKitPersonalities"]["Surface Serial Hub"].get("SL4SAMWakeEnabled") is True
    binary = builder.OUT / "VoodooGPIO.kext/Contents/MacOS/VoodooGPIO"
    strings = subprocess.check_output(["/usr/bin/strings", str(binary)], text=True)
    forbidden = ("SL4LidGPIOProbe", "SL4LidGPEArmStatus", "SL4LidGPERecoveryCount",
                 "SL4LidResume", "SL4SAMWakeArmed", "SL4SAMWakeGPIO",
                 "Armed SAM wake", "Disarmed SAM wake", "SAM GPIO wake")
    leftovers = [token for token in forbidden if token in strings]
    if leftovers:
        raise RuntimeError("Diagnostic telemetry remains in production VoodooGPIO: " + ", ".join(leftovers))
    print("PRODUCTION CHECKS PASSED: VoodooGPIO 1.2.5, BigSurface 1.2.1, no temporary diagnostic telemetry.")
