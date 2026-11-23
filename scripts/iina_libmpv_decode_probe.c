/*
 * Headless libmpv playback check with IINA's own signed libmpv and bundled
 * FFmpeg decoders. Doesn't install or change any system settings.
 * Compile with -Wl,-rpath,<IINA.app/Contents/Frameworks> and -ldl.
 */
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef struct mpv_handle mpv_handle;
typedef struct {
    int event_id;
    int error;
    uint64_t reply_userdata;
    void *data;
} mpv_event;
typedef struct { int reason; int error; int playlist_entry_id; int playlist_insert_id; } mpv_event_end_file;
#define MPV_EVENT_END_FILE 7
#define MPV_EVENT_FILE_LOADED 8
#define MPV_EVENT_SHUTDOWN 1
#define MPV_FORMAT_INT64 4

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s /absolute/path/libmpv.2.dylib /absolute/path/video\n", argv[0]);
        return 4;
    }
    void *lib = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!lib) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 4; }
    mpv_handle *(*create)(void) = dlsym(lib, "mpv_create");
    int (*setopt)(mpv_handle*, const char*, const char*) = dlsym(lib, "mpv_set_option_string");
    int (*initialize)(mpv_handle*) = dlsym(lib, "mpv_initialize");
    int (*command)(mpv_handle*, const char**) = dlsym(lib, "mpv_command");
    const mpv_event *(*wait_event)(mpv_handle*, double) = dlsym(lib,"mpv_wait_event");
    char *(*get_string)(mpv_handle*, const char*)=dlsym(lib,"mpv_get_property_string");
    int (*get_property)(mpv_handle*, const char*, int, void*)=dlsym(lib,"mpv_get_property");
    void (*free_property)(void*) = dlsym(lib,"mpv_free");
    void (*destroy)(mpv_handle*) = dlsym(lib,"mpv_terminate_destroy");
    if(!create||!setopt||!initialize||!command||!wait_event||!get_string||!get_property||!free_property||!destroy) {
        fputs("Incomplete libmpv API\n",stderr); return 4;
    }
    mpv_handle *mpv = create();
    if(!mpv) { fputs("mpv_create failed\n",stderr);return 4; }
    const char *kvs[][2]={
        {"config","no"},{"vo","null"},{"ao","null"},{"hwdec","no"},
        {"input-default-bindings","no"},{"terminal","no"},{"idle","no"},
        {"keep-open","no"},{"osc","no"},{"ytdl","no"},{"video","auto"},
        {"vid","auto"},{"aid","no"},{"untimed","yes"},{"vd-lavc-threads","4"}
    };
    for(size_t i=0;i<sizeof(kvs)/sizeof(kvs[0]);i++){
        int rc=setopt(mpv,kvs[i][0],kvs[i][1]);
        if(rc<0)fprintf(stderr,"OPTION %s failed %d\n",kvs[i][0],rc);
    }
    int err=initialize(mpv);
    if(err<0){fprintf(stderr,"mpv_init failed: %d\n",err);destroy(mpv);return 4;}
    const char *cmd[]={"loadfile",argv[2],"replace",NULL};
    err=command(mpv,cmd);
    if(err<0){fprintf(stderr,"mpv loadfile failed %d\n",err);destroy(mpv);return 4;}
    int loaded=0, eof=0, enderr=0;
    int64_t width=0,height=0,decoded_dropped=-1;
    char *codec=NULL;
    time_t started=time(NULL);
    while(time(NULL)-started<45){
        const mpv_event *event=wait_event(mpv,0.6);
        if(!event)continue;
        if(event->event_id==MPV_EVENT_FILE_LOADED){
            loaded=1;
            if(codec)free_property(codec);
            codec=get_string(mpv,"video-codec");
            get_property(mpv,"width",MPV_FORMAT_INT64,&width);
            get_property(mpv,"height",MPV_FORMAT_INT64,&height);
            printf("FILE_LOADED CODEC=%s SIZE=%lldx%lld\n",codec?codec:"<none>",(long long)width,(long long)height);
            fflush(stdout);
        }
        if(event->event_id==MPV_EVENT_END_FILE){
            const mpv_event_end_file *e=(const mpv_event_end_file*)event->data;
            if(e){eof=(e->reason==0);enderr=e->error;}
            break;
        }
        if(event->event_id==MPV_EVENT_SHUTDOWN)break;
    }
    get_property(mpv,"decoder-frame-drop-count",MPV_FORMAT_INT64,&decoded_dropped);
    printf("RESULT codec=%s dimensions=%lldx%lld file_loaded=%d eof=%d end_error=%d decoder_dropped=%lld hardware_decode=no\n",
            codec?codec:"<none>",(long long)width,(long long)height,loaded,eof,enderr,(long long)decoded_dropped);
    if(codec)free_property(codec);
    destroy(mpv);
    dlclose(lib);
    return loaded && eof && !enderr && width>0 && height>0 ? 0:2;
}
