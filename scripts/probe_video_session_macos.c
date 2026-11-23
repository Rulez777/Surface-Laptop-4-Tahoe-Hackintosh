/*
 * Read-only macOS VideoToolbox hardware-required decoder-session probe.
 * Build:
 * clang -O2 -Wall -Wextra -framework CoreFoundation -framework CoreMedia \
 *       -framework VideoToolbox probe_video_session_macos.c -o probe-vt
 *
 * This is a session-creation test; it does NOT decode sample frames.
 * Using codec-parameter-free format descriptions can fail even for supported
 * hardware. Never advertise true hardware decode based on this test alone.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <CoreMedia/CoreMedia.h>
#include <VideoToolbox/VideoToolbox.h>
#include <stdio.h>
#include <stdint.h>

typedef struct {
    const char *name;
    CMVideoCodecType type;
} Codec;

static int session_status(CMFormatDescriptionRef format, bool require_hw, bool *uses_hw) {
    CFMutableDictionaryRef spec = NULL;
    if (require_hw) {
        spec = CFDictionaryCreateMutable(kCFAllocatorDefault, 0,
                        &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
        if (!spec) return -1;
        CFDictionarySetValue(spec,
                            kVTVideoDecoderSpecification_RequireHardwareAcceleratedVideoDecoder,
                            kCFBooleanTrue);
    }
    VTDecompressionSessionRef session = NULL;
    OSStatus status = VTDecompressionSessionCreate(kCFAllocatorDefault, format, spec,
                                                  NULL, NULL, &session);
    if (spec) CFRelease(spec);
    if (!status && session) {
        CFTypeRef property = NULL;
        if (VTSessionCopyProperty(session,
                kVTDecompressionPropertyKey_UsingHardwareAcceleratedVideoDecoder,
                kCFAllocatorDefault, &property) == noErr && property) {
            *uses_hw = CFGetTypeID(property) == CFBooleanGetTypeID() &&
                       CFBooleanGetValue((CFBooleanRef)property);
            CFRelease(property);
        }
        VTDecompressionSessionInvalidate(session);
        CFRelease(session);
    }
    return (int)status;
}

int main(void) {
    const Codec codecs[] = {
        {"H.264", kCMVideoCodecType_H264},
        {"HEVC", kCMVideoCodecType_HEVC},
        {"VP9", kCMVideoCodecType_VP9},
        {"AV1", kCMVideoCodecType_AV1}
    };
    printf("{\n  \"probe\": \"VideoToolbox ephemeral session creation\",\n");
    printf("  \"changes_to_system\": false,\n");
    printf("  \"real_frame_decode_tested\": false,\n");
    printf("  \"codecs\": [\n");
    for (unsigned i = 0; i < sizeof(codecs)/sizeof(codecs[0]); ++i) {
        CMVideoFormatDescriptionRef format = NULL;
        OSStatus fm = CMVideoFormatDescriptionCreate(kCFAllocatorDefault,
                        codecs[i].type, 1920, 1080, NULL, &format);
        bool hw = false, sw = false;
        int hw_status = fm ? (int)fm : session_status(format, true, &hw);
        int any_status = fm ? (int)fm : session_status(format, false, &sw);
        printf("    {\"codec\": \"%s\", \"fourcc\": \"%c%c%c%c\", "
               "\"api_advertised\": %s, \"format_status\": %d, "
               "\"hardware_required_status\": %d, "
               "\"hardware_required_session_reported_hw\": %s, "
               "\"unrestricted_status\": %d, "
               "\"unrestricted_session_reported_hw\": %s}%s\n",
               codecs[i].name,
               (char)(codecs[i].type >> 24), (char)(codecs[i].type >> 16),
               (char)(codecs[i].type >> 8), (char)(codecs[i].type),
               VTIsHardwareDecodeSupported(codecs[i].type) ? "true" : "false",
               (int)fm, hw_status, hw ? "true" : "false",
               any_status, sw ? "true" : "false",
               i + 1 < sizeof(codecs)/sizeof(codecs[0]) ? "," : "");
        if (format) CFRelease(format);
    }
    printf("  ],\n  \"notes\": \"Session creation is not stream decode; a format may "
           "require codec-specific sample descriptions.\"\n}\n");
    return 0;
}
