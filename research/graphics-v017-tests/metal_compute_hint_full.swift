import Foundation
import Metal
guard let gpu=MTLCreateSystemDefaultDevice(),let q=gpu.makeCommandQueue() else {exit(3)}
// New test source: exercise real workgroup sizes and group-local barrier.
let lib=try gpu.makeLibrary(source:"""
#include <metal_stdlib>
using namespace metal;
kernel void fullGroupTest(device uint *out [[buffer(0)]],
   uint global [[thread_position_in_grid]], uint local [[thread_index_in_threadgroup]],
   uint dim [[threads_per_threadgroup]]) {
   threadgroup uint values[1024];
   values[local]=global*13u+11u;
   threadgroup_barrier(mem_flags::mem_threadgroup);
   out[global]=values[(local+1u)%dim];
}
""",options:nil)
let fn=lib.makeFunction(name:"fullGroupTest")!
var all=true
for hint in [0,1,32,48,64,256,1024] {
    let width=hint==0 ? 64:hint
    let d=MTLComputePipelineDescriptor()
    d.computeFunction=fn
    if hint>0 {d.maxTotalThreadsPerThreadgroup=hint}
    do {
        let p=try gpu.makeComputePipelineState(descriptor:d,options:[],reflection:nil)
        guard p.maxTotalThreadsPerThreadgroup>=width else {print("FULL hint=\(hint) max too low");all=false;continue}
        let n=width*2
        let buf=gpu.makeBuffer(length:n*4,options:.storageModeShared)!
        let c=q.makeCommandBuffer()!
        let e=c.makeComputeCommandEncoder()!
        e.setComputePipelineState(p);e.setBuffer(buf,offset:0,index:0)
        e.dispatchThreadgroups(MTLSize(width:2,height:1,depth:1),threadsPerThreadgroup:MTLSize(width:width,height:1,depth:1))
        e.endEncoding();c.commit();c.waitUntilCompleted()
        let a=buf.contents().bindMemory(to:UInt32.self,capacity:n)
        let good=c.status == .completed && (0..<n).allSatisfy{let b=($0/width)*width+($0+1)%width;return a[$0]==UInt32(b*13+11)}
        print("FULL hint=\(hint) threads=\(width) pipeline=PASS output=\(good ? "PASS":"FAIL") max=\(p.maxTotalThreadsPerThreadgroup)")
        all = all && good
    } catch {print("FULL hint=\(hint) pipeline=FAIL error=\(error)");all=false}
    fflush(stdout)
}
exit(all ? 0:2)
