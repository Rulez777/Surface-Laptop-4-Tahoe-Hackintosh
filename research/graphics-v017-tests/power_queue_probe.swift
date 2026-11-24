import Foundation
import Metal
guard let gpu=MTLCreateSystemDefaultDevice(),let q=gpu.makeCommandQueue() else {exit(3)}
let lib=try gpu.makeLibrary(source:"""
#include <metal_stdlib>
using namespace metal;
kernel void powerTest(device uint *out [[buffer(0)]],uint i [[thread_position_in_grid]]) {
    uint x=i+17;
    for(uint j=0;j<384;j++) {x=x*1664525u+1013904223u; x^=(x>>13); x^=(x<<9);}
    out[i]=x;
}
""",options:nil)
let state=try gpu.makeComputePipelineState(function:lib.makeFunction(name:"powerTest")!)
let count=131072, depth=4
let bufs=(0..<depth).map{_ in gpu.makeBuffer(length:count*4,options:.storageModeShared)!}
var pending:[(MTLCommandBuffer,Double)]=[],latencies:[Double]=[],gpuMs:[Double]=[]
var submitted=0,completed=0,failed=0,peak=0
let start=ProcessInfo.processInfo.systemUptime
print("START bounded GPU load");fflush(stdout)
func drain() {
    while let head=pending.first, head.0.status == .completed || head.0.status == .error {
        pending.removeFirst()
        if head.0.status == .error {failed+=1; print("GPU_ERROR \(String(describing:head.0.error))");break}
        completed+=1
        latencies.append((ProcessInfo.processInfo.systemUptime-head.1)*1000)
        if head.0.gpuEndTime>head.0.gpuStartTime {gpuMs.append((head.0.gpuEndTime-head.0.gpuStartTime)*1000)}
    }
}
var nextReport=start+1
while ProcessInfo.processInfo.systemUptime-start<10 && failed==0 {
    drain()
    if pending.count<depth {
        let c=q.makeCommandBuffer()!,e=c.makeComputeCommandEncoder()!
        e.setComputePipelineState(state);e.setBuffer(bufs[submitted%depth],offset:0,index:0)
        e.dispatchThreads(MTLSize(width:count,height:1,depth:1),threadsPerThreadgroup:MTLSize(width:64,height:1,depth:1))
        e.endEncoding()
        let t=ProcessInfo.processInfo.systemUptime;c.commit();pending.append((c,t));submitted+=1;peak=max(peak,pending.count)
    } else {
        Thread.sleep(forTimeInterval:0.0005)
    }
    let now=ProcessInfo.processInfo.systemUptime
    if now>=nextReport {
        print("t=\(String(format:"%.1f",now-start)) submitted=\(submitted) completed=\(completed) pending=\(pending.count)")
        fflush(stdout);nextReport+=1
    }
    if let h=pending.first, ProcessInfo.processInfo.systemUptime-h.1>3 {print("COMMAND_TIMEOUT");failed+=1;break}
}
let deadline=ProcessInfo.processInfo.systemUptime+3
while !pending.isEmpty && failed==0 && ProcessInfo.processInfo.systemUptime<deadline {drain();Thread.sleep(forTimeInterval:0.001)}
func percentile(_ a:[Double],_ q:Double)->Double {let s=a.sorted();return s.isEmpty ? -1:s[min(s.count-1,Int(Double(s.count-1)*q))]}
print("RESULT submitted=\(submitted) completed=\(completed) pending=\(pending.count) errors=\(failed) peak=\(peak) p50_ms=\(percentile(latencies,0.5)) p95_ms=\(percentile(latencies,0.95)) max_ms=\(latencies.max() ?? -1) gpu_p50_ms=\(percentile(gpuMs,0.5))")
exit(failed==0 && pending.isEmpty && completed==submitted ? 0:2)
