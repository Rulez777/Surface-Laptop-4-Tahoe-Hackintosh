# Browser video — Surface Laptop 4 Intel / macOS Tahoe

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

Open YouTube using **Safari** and test a standard 1080p video. YouTube's **Stats for nerds** can reveal the active codec. The confirmed working stream used H.264 (`avc1`). This device advertises hardware H.264 and HEVC decoding but **not hardware VP9 or AV1**. Safari may select a different codec for other videos, resolutions or streams; those paths are not established by this test.

If the video stalls, record the codec, resolution and whether audio continues. Check the script output, driver versions and macOS logs before changing settings. A browser/network problem and a VideoToolbox failure require different fixes.

## Limitations

- Playback was confirmed only for the observed Safari/YouTube H.264 case; this is **not universal video compatibility** or guaranteed performance for other codecs, protected media, fullscreen scaling or every hardware revision.
- Known upstream Tiger Lake VideoToolbox and AppleGVA issues may still affect particular media operations: [WhateverXe issue #92](https://github.com/b00t0x/WhateverXe/issues/92), [issue #96](https://github.com/b00t0x/WhateverXe/issues/96) and [issue #129](https://github.com/b00t0x/WhateverXe/issues/129). Graphics 0.4.4 includes a CPU image-conversion fallback but does not resolve every possible GVA failure.
- Avoid deleting AppleIntelTGLGraphicsVADriver, disabling GVA globally or adding unverified video boot arguments. Such workarounds can break Metal, fullscreen playback, WindowServer or protected playback.
- This project does not modify or redistribute the signed WhateverXe Graphics package. Its pinned original download and SHA-256 are verified by the driver-pack builder.
