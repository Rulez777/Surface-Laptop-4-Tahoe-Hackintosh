#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <dlfcn.h>
typedef int (*Build)(void *, const void *, size_t, unsigned, const void *, size_t,
                      void **,void **,void **,void **,void **,void **,const char **);
static unsigned calls=0;
static int backend(const void *air,unsigned length,void *ctx,const void *options,void **out,void *release,unsigned flags){
    (void)air;(void)ctx;(void)options;(void)release;(void)flags;
    assert(length==16); *out=NULL; calls++; return 123;
}
static void trial(Build f,unsigned hint,int extra,unsigned suffix,int expect){
    _Alignas(16) unsigned char ctx[0x160]={0},state[0xd8]={0},air[16]={0};
    void *outs[6]; for(int i=0;i<6;i++)outs[i]=(void*)1;
    const char *error=NULL; void *cb=(void*)backend;
    memcpy(ctx+0x28,&cb,8); state[0]=3; state[0xd7]=suffix; memcpy(state+0x9c,&hint,4);
    if(extra>=0)state[extra]=1;
    unsigned before=calls;
    int r=f(ctx,state,sizeof state,0,air,sizeof air,&outs[0],&outs[1],&outs[2],&outs[3],&outs[4],&outs[5],&error);
    assert(r==1 && error);
    assert(calls-before==(unsigned)expect);
    for(int i=0;i<6;i++)assert(outs[i]==NULL);
    if(expect)assert(strstr(error,"IGC compile status 123"));
    else assert(strstr(error,"unsupported compute state") || strstr(error,"unsupported compute suffix"));
}
int main(int argc,char **argv){
    assert(argc==3);
    void *a=dlopen(argv[1],RTLD_LOCAL|RTLD_NOW),*b=dlopen(argv[2],RTLD_LOCAL|RTLD_NOW);
    assert(a&&b);Build old=(Build)dlsym(a,"XeBuildUntranslated"),candidate=(Build)dlsym(b,"XeBuildUntranslated");assert(old&&candidate);
    unsigned n=0;
    trial(old,0,-1,1,1); n++;
    for(unsigned x=1;x<=1024;x++){trial(old,x,-1,1,0);trial(candidate,x,-1,1,1);n+=2;}
    trial(candidate,0,-1,1,1);n++;
    trial(candidate,1025,-1,1,0);n++;
    trial(candidate,UINT32_MAX,-1,1,0);n++;
    for(int j=4;j<215;j++){if(j>=156&&j<160)continue;trial(candidate,64,j,1,0);n++;}
    trial(candidate,64,-1,0,0);trial(candidate,64,-1,2,0);n+=2;
    printf("FULL_ADAPTER_ENTRY_TEST_PASS %u cases; real adapter entry and mock backend; no shader compilation.\n",n);
    return 0;
}
