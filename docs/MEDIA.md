# Browser video — Surface Laptop 4 Intel / macOS Tahoe

**2026-11-23 hardware-codec audit:** [Intel Tiger Lake AV1/VP9 vs macOS VideoToolbox registry](VIDEO-CODECS-20261123.md). The Intel Xe-LP media block supports AV1/VP9 decoding, but on the tested macOS installation the hardware decoder API returns false and the decoder capability dictionaries are null. **No AV1/VP9 hardware fix has been validated.** Calling VideoToolbox's supplemental codec registration API in a standalone diagnostic process did not enable hardware AV1 or VP9. New all-in-one builds from this source include a read-only diagnostic, `scripts/audit_codec_macos.py` (the existing published v0.5.0 archive is unchanged); it does not modify drivers or system settings.

**Verified on one machine:** macOS Tahoe 26.7.1, Intel Iris Xe `8086:9A49`, WhateverXe 0.8.3, WhateverXe Graphics 0.4.4. Safari played a YouTube H.264 (`avc1`) stream at **1920 × 1080**. WebKit's media logs showed the video timebase advancing, hundreds of decoded frames and zero dropped frames during the recorded sample.

## Required graphics configuration

Use the [main installation instructions](../README.md#1-graphics--metal-2) to install the official **WhateverXe Graphics 0.4.4** package alongside **WhateverXe 0.8.3**. Do not substitute an older package or overwrite the signed Graphics payload. The installer includes the Tahoe compatibility setting:

`/Library/Preferences/FeatureFlags/Domain/CoreMedia.plist` → `AllowOnePassMetalScaling:Enabled=false`.

That setting was already present on the test device when YouTube began playing. We did **not** introduce an unverified driver patch or extra boot argument.

After completing the graphics stage, run this **read-only** test in macOS Terminal:

```bash
python3 "$HOME/Downloads/SL4-Tahoe-Git/scripts/verify_video_macos.py"
```

The same script is bundled in the generated `SL4-FULL-DRIVERS/macOS-Installers/` directory. A **YES** result means the detected software prerequisites match the tested laptop, **not** that every YouTube video will play.

## Browser check

Open YouTube using **Safari** and test a standard 1080p video. YouTube's **Stats for nerds** can reveal the active codec. The confirmed working stream used H.264 (`avc1`). This macOS installation advertises hardware H.264 and HEVC decoding but **does not expose hardware VP9 or AV1**, despite the Intel GPU's documented media capabilities. Safari may select a different codec for other videos, resolutions or streams; those paths are not established by this test.

If the video stalls, record the codec, resolution and whether audio continues. Check the script output, driver versions and macOS logs before changing settings. A browser/network problem and a VideoToolbox failure require different fixes.

## AV1/VP9 web-video fallback verified on this Surface (2026-11-23)

On this exact macOS Tahoe 26.7.1 machine, Mozilla Firefox **160.0.1** was installed into `~/Applications/Firefox.app` from the official Mozilla download. The app's notarized Apple Developer ID signature was verified as **Mozilla Corporation / Team ID `43AQ936H96`**. Safari, the default browser, GPU drivers, EFI and sleep settings were left unchanged.

An **isolated Firefox WebDriver session** played real 10-second sample videos with the HTML5 `video` element. Playback time advanced beyond 2 seconds in each clip, and Firefox reported the following decoded frames and resolution:

| Codec/container | Sample | Frames decoded | Dropped | Browser playback |
| --- | --- | ---: | ---: | --- |
| AV1/MP4 | 640 × 360 | 69 | 0 | Pass |
| VP9/WebM | 640 × 360 | 69 | 2 | Pass |
| AV1/MP4 | 1920 × 1080 | 68 | 0 | Pass |
| VP9/WebM | 1920 × 1080 | 68 | 2 | Pass |

Samples: `https://test-videos.co.uk/` (Big Buck Bunny 10-second AV1 MP4 / VP9 WebM, sizes 1 MB and 5 MB). These are **software playback tests**, not Intel fixed-function decoder tests. Playback at 4K, 10-bit, HDR, YouTube DRM and other applications is not established by these four samples.

The Windows-first all-in-one now includes **opt-in**, no-admin `install_media_fallback_macos.py` for the same software fallback. In macOS Terminal with the full project checkout, run a **single command**: `python3 scripts/install_media_fallback_macos.py --install`. Or launch `QuickStart-Mac.command --media-fallback` from a newly built `SL4DATA` installer package, or choose advanced menu **4**. No change to the normal installer path or default browser. `--check --json` reports an existing verified Firefox without installing anything. It always refuses unsigned, unnotarized or non-Mozilla app bundles.

## Limitations

- Additional controlled tests of local files in a dedicated WebKit view (the engine used by Safari) confirmed **H.264, HEVC and VP8 playback** at 480×270, 24 fps. VP9 did not advance or render frames, and AV1 returned `NotSupportedError`. This is **not universal browser video compatibility** or guaranteed performance for other resolutions, codecs, protected media, fullscreen scaling or hardware revisions.
- Known upstream Tiger Lake VideoToolbox and AppleGVA issues may still affect particular media operations: [WhateverXe issue #92](https://github.com/b00t0x/WhateverXe/issues/92), [issue #96](https://github.com/b00t0x/WhateverXe/issues/96) and [issue #129](https://github.com/b00t0x/WhateverXe/issues/129). Graphics 0.4.4 includes a CPU image-conversion fallback but does not resolve every possible GVA failure.
- Avoid deleting AppleIntelTGLGraphicsVADriver, disabling GVA globally or adding unverified video boot arguments. Such workarounds can break Metal, fullscreen playback, WindowServer or protected playback.
- This project does not modify or redistribute the signed WhateverXe Graphics package. Its pinned original download and SHA-256 are verified by the driver-pack builder.

## Local codec playback results (2026-11-22)

These tests used a dedicated macOS `WKWebView`, **not a regular Safari tab**. Each locally generated six-second sample contained 480×270 video at 24 fps and audio, and was played with an HTML `video` element. WebKit playback time, decode counts, errors and dropped frames were captured. All results refer to the single tested Intel Surface Laptop 4.

| Codec / container | WebKit playback | Frames decoded | Dropped | Hardware decode |
| --- | --- | ---: | ---: | --- |
| H.264 / MP4 | Working | 181 | 2 | Confirmed in WebKit GPU logs |
| HEVC / MP4 | Working | 183 | 0 | Confirmed in WebKit GPU logs |
| VP8 / WebM | Working | 185 | 0 | Not established |
| VP9 / WebM | Does not start (0 s) | 0 | 0 | Not advertised |
| AV1 / MP4 | `NotSupportedError` (code 4) | 0 | 0 | Not advertised |

Independent FFmpeg software decoding of the **same VP9 and AV1 files succeeded**. This demonstrates CPU decoding can work with a bundled decoder, not that WebKit includes one.

The original YouTube test separately confirmed **Safari H.264 1920×1080 playback** via VideoToolbox, with successful frame progression. The local codec experiment is a compatibility baseline, **not a repair**. No EFI settings, Apple drivers, or macOS system preferences were modified.
