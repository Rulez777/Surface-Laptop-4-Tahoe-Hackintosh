# Surface Laptop 4 / Iris Xe — AV1 and VP9 codec audit

Date: 2026-11-23. Device: Microsoft Surface Laptop 4 13.5", Intel i7-1185G7,
Iris Xe PCI ID `8086:9A49`, macOS Tahoe 26.7.1 (25G241).

## Official Tiger Lake silicon capability

Intel's **11th Generation Intel Core Processor, Datasheet Volume 1**,
section 9.1.1 and Tables 9-1/9-2, specify the following fixed-function
media features. These are **hardware specifications, not macOS support claims**.

| Codec | Intel hardware decode | Intel hardware encode |
| --- | --- | --- |
| AV1 | Profile 0, 4:2:0, 8/10-bit, up to 4K × 2K video per Table 9-1 | Not listed |
| VP9 | Profile 0 4:2:0 8-bit, Profile 1 4:4:4 8-bit, Profile 2 4:2:0 10/12-bit; see Intel's resolution/profile table | Yes, with partial high-bit-depth profile support |
| HEVC | Yes, Main and listed higher chroma/bit-depth profiles | Yes |
| H.264 | Yes, up to 4K 60 fps for 4:2:0 8-bit | Yes |
| MPEG-2 | Yes, Main up to 1080p | Mentioned in encoder overview; verify actual implementation |
| VC-1/WMV9 | Yes | Not listed |
| JPEG/MJPEG | Yes | JPEG |

Official Intel source:
https://cdrdv2-public.intel.com/631121/631121_TGL%20Datasheet%20Volume1of2%20rev012_PUBLIC.pdf

The Intel specification does not guarantee that every profile can be driven
through Apple's VideoToolbox API or that these maxima apply to every workload.

## Live macOS observations

Read-only checks on 2026-11-23 established:

- Loaded Lilu 1.7.2, WhateverXe 0.8.3, AppleIntelTGLCompat 0.8.1,
  AppleIntelTGLGraphics 16.0.0 and AppleIntelTGLGraphicsFramebuffer 16.0.0.
- Graphics present as Intel Iris Xe, `0x9a49`; Metal 2 reported.
- WhateverXe Graphics Common and Tahoe packages both `0.4.4`.
- CoreMedia `AllowOnePassMetalScaling.Enabled=false` still in effect.
- `VTIsHardwareDecodeSupported` is true for `avc1` and `hvc1`;
  false for `vp09` and `av01`.
- A scoped test calling `VTRegisterSupplementalVideoDecoderIfAvailable` for
  `av01` and `vp09` in an isolated process did **not** change either false
  hardware-decode result. Registering professional VideoToolbox codecs also
  left both false. This rules out a simple supplemental registration toggle
  on the tested system, but not a future decoder implementation.
- `VTCopyAV1DecoderCapabilitiesDictionary` returns null;
  `VTCopyVP9DecoderCapabilitiesDictionary` returns null.
- `VTCopyHEVCDecoderCapabilitiesDictionary` returns a capability dictionary,
  including hardware-assisted entries.
- `VTCopyVideoEncoderList` registers Apple H.264 (HW), H.264 (SW),
  HEVC (SW), but no hardware HEVC, VP9 or AV1 encoder on this macOS install.
  This says nothing conclusive about the Intel hardware's encode capability.
- The installed Intel VA user-space bundle is
  `/Library/GPUBundles/AppleIntelTGLGraphicsVADriver.bundle`, bundle version
  `16.0.32`. Read-only binary-string inspection found AV1 decode-control
  messages (`AV1 Decode Driver S2L Enable Flag`, AV1 rowstore-cache flags)
  and VP9 media flags. These strings indicate codec-related code/data but
  **do not prove a functional VideoToolbox decoder implementation**.
- Prior controlled WebKit tests, documented in [MEDIA.md](MEDIA.md),
  reproduced AV1 `NotSupportedError` and VP9 playback stall. They were
  **not** hardware-decoding tests of high-resolution/10-bit samples.
- Windows 11 Intel-driver hardware-query comparison has **not yet been run**
  in this session because this same Surface was booted into macOS.

The audit script is `scripts/audit_codec_macos.py`. To reproduce
on installed macOS:

`python3 scripts/audit_codec_macos.py --json`

Optional isolated-process registration probe:
`python3 scripts/audit_codec_macos.py --probe-supplemental --json`

Neither option changes OS preferences or the installed graphics stack.

The output is a **capability/registry probe**, not proof of actual decoded
frames. Even a future "true" response needs verification from a real video
stream and decoder/GPU telemetry.

## Working software compatibility path (2026-11-23)

- Official Mozilla Firefox 160.0.1 installed into the user's
  `~/Applications/Firefox.app` with verified Apple Developer ID signature
  (Mozilla Corporation, Team ID `43AQ936H96`) and Gatekeeper notarization.
- Isolated real browser playback tests passed 10-second AV1/MP4 and VP9/WebM
  at both 640×360 and 1920×1080. Firefox's HTML5 `getVideoPlaybackQuality`
  reported ~68–69 actual decoded frames and fewer than three drops by 2.3 s.
- This is a **software codec fallback**. No AV1/VP9 hardware path in Intel
  media-engine / VideoToolbox was unlocked or advertised.
- Opt-in `scripts/install_media_fallback_macos.py --install` safely deploys
  notarized Mozilla Firefox for users who need AV1/VP9 web playback.
  Existing Firefox is never overwritten. User browser defaults, EFI, sleep,
  graphics and CoreMedia settings are unchanged. The helper ships in the
  new Windows-first and offline kits, but does not run automatically.
- Alternative experimental graphics driver `zep245/IrisXe-macos-driver` claims
  Intel Tiger Lake hardware AV1 decoding using a **different i915/NMXGPU,
  Mesa ANV Vulkan and VideoToolbox pipeline**; its VP9 GPU path remains off.
  It would replace the current display/Metal/sleep stack and is not qualified
  for the Surface's eDP/DMC/RCS fixes. **Do not install it over this system**.
  Source: https://github.com/zep245/IrisXe-macos-driver

## Current engineering conclusion

The Tiger Lake media engine supports AV1 and VP9 decoding in hardware, but
**VideoToolbox on this machine does not currently advertise hardware support**
for either codec, and the AV1/VP9 capability dictionaries return null.
A single hidden preference or playback success cannot establish true
fixed-function GPU decoding.

For hardware AV1/VP9 to become available, the system must supply a functioning
decoder path through VideoToolbox → AppleGVA → Intel VA media driver → Intel
media engine, with valid codec profile/session support. The investigation has
**not yet proven which component prevents AV1/VP9 registration**, nor that
the existing signed donor driver implements them. Generic software AV1/VP9
playback or shader-based Metal acceleration does not meet the goal of
Intel hardware media-block decoding.

Next technical investigations:

1. Inspect AppleIntelTGLGraphicsVADriver and AppleGVA codec identifiers,
   support tables and decoder factories, comparing against Intel's documented
   media command pipeline. Avoid modifications to signed system binaries.
2. Acquire controlled AV1/VP9 1080p, 4K and 10-bit samples; independently
   test native VideoToolbox and browser paths while collecting actual decoder
   type, engine utilization and GPU logs.
3. If a compatible VA decoder is demonstrably present but excluded by a
   device/board capability check, develop a reversible, narrowly-scoped
   correction, then repeat all H.264/HEVC/Metal/sleep/wake regressions.
4. Integrate only proven codec fixes into the Windows-first all-in-one installer.
   **Do not** enable undocumented boot flags or spoof successful decoding.

## Delivery and safety

The **read-only diagnostic** is included when building the offline toolkit,
Windows QuickStart kit, Windows-generated installer/repair staging, and full
driver pack under `macOS-Installers` **from these updated sources**. Already
published v0.5.0 release assets were not modified. No EFI, NVRAM, pmset, boot mode,
Windows partition, audio, sleep, existing eDP/DMC/RCS kext or signed
graphics payload was changed during this audit.

Hardware AV1/VP9 **is not unlocked** by this diagnostic and must not be
advertised as functional until proven by controlled decoding tests.
