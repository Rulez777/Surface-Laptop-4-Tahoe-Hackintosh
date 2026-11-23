/*
 * Probe real compressed video stream descriptions with VideoToolbox.
 *
 * Compiles only on macOS with Command Line Tools:
 *   clang -fobjc-arc -O2 -Wall -Wextra -framework Foundation \
 *     -framework AVFoundation -framework VideoToolbox -framework CoreMedia \
 *     probe_real_asset_sessions_macos.m -o probe_real_assets
 *
 * Run: probe_real_assets input1.mp4 input2.webm
 *
 * No driver or global setting is modified. A session creation success alone
 * does not establish that frames are actually decoded by the Intel media block.
 */
#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>
#import <VideoToolbox/VideoToolbox.h>
#import <CoreMedia/CoreMedia.h>

static NSString *fourcc(CMVideoCodecType codec) {
    char s[5] = {(char)(codec >> 24), (char)(codec >> 16),
                 (char)(codec >> 8), (char)codec, 0};
    for (int i = 0; i < 4; i++) if (s[i] < 32 || s[i] > 126) s[i] = '?';
    return [NSString stringWithUTF8String:s];
}

static NSDictionary *sessionProbe(CMFormatDescriptionRef format, BOOL requireHW) {
    CFMutableDictionaryRef spec = NULL;
    if (requireHW) {
        spec = CFDictionaryCreateMutable(kCFAllocatorDefault, 0,
                                        &kCFTypeDictionaryKeyCallBacks,
                                        &kCFTypeDictionaryValueCallBacks);
        CFDictionarySetValue(spec,
            kVTVideoDecoderSpecification_RequireHardwareAcceleratedVideoDecoder,
            kCFBooleanTrue);
    }
    VTDecompressionSessionRef session = NULL;
    OSStatus status = VTDecompressionSessionCreate(kCFAllocatorDefault, format,
                                                   spec, NULL, NULL, &session);
    if (spec) CFRelease(spec);
    BOOL reportedHW = NO;
    BOOL reportsHWProperty = NO;
    if (status == noErr && session) {
        CFTypeRef state = NULL;
        if (VTSessionCopyProperty(session,
                kVTDecompressionPropertyKey_UsingHardwareAcceleratedVideoDecoder,
                kCFAllocatorDefault, &state) == noErr && state != NULL) {
            reportsHWProperty = YES;
            if (CFGetTypeID(state) == CFBooleanGetTypeID()) {
                reportedHW = CFBooleanGetValue((CFBooleanRef)state);
            }
            CFRelease(state);
        }
        VTDecompressionSessionInvalidate(session);
        CFRelease(session);
    }
    return @{@"os_status": @(status),
             @"session_created": @(status == noErr),
             @"hardware_property_reported": @(reportsHWProperty),
             @"hardware_reported": @(reportedHW)};
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSMutableArray *results = [NSMutableArray array];
        for (int i = 1; i < argc; i++) {
            NSString *path = [NSString stringWithUTF8String:argv[i]];
            NSMutableDictionary *result = [NSMutableDictionary dictionaryWithObject:path.lastPathComponent
                                                                              forKey:@"path"];
            @try {
                NSURL *url = [NSURL fileURLWithPath:path];
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
                AVURLAsset *asset = [AVURLAsset URLAssetWithURL:url options:nil];
                NSArray<AVAssetTrack *> *tracks = [asset tracksWithMediaType:AVMediaTypeVideo];
#pragma clang diagnostic pop
                if (!tracks.count) {
                    result[@"error"] = @"AVFoundation did not recognize a video track";
                } else {
                    AVAssetTrack *track = tracks.firstObject;
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
                    NSArray *formats = track.formatDescriptions;
#pragma clang diagnostic pop
                    if (!formats.count) {
                        result[@"error"] = @"AVFoundation did not expose codec format description";
                    } else {
                        CMFormatDescriptionRef format = (__bridge CMFormatDescriptionRef)formats.firstObject;
                        CMVideoCodecType codec = CMFormatDescriptionGetMediaSubType(format);
                        result[@"codec_fourcc"] = fourcc(codec);
                        result[@"video_toolbox_advertises_hardware"] =
                            @(VTIsHardwareDecodeSupported(codec));
                        result[@"require_hardware"] = sessionProbe(format, YES);
                        result[@"allow_software"] = sessionProbe(format, NO);
                        result[@"real_frame_decode_tested"] = @NO;
                    }
                }
            } @catch (NSException *exception) {
                result[@"error"] = exception.reason ?: @"Unknown AVFoundation exception";
            }
            [results addObject:result];
        }
        NSDictionary *report = @{
            @"method": @"Read-only real asset format description and VideoToolbox session creation",
            @"has_decoded_frames": @NO,
            @"devices_or_drivers_modified": @NO,
            @"assets": results
        };
        NSData *data = [NSJSONSerialization dataWithJSONObject:report
                                                       options:NSJSONWritingPrettyPrinted
                                                         error:nil];
        if (!data) return 2;
        fwrite(data.bytes, 1, data.length, stdout);
        fputc('\n', stdout);
        return 0;
    }
}
