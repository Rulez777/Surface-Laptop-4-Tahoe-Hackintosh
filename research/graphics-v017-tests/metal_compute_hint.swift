import Foundation
import Metal

guard let gpu = MTLCreateSystemDefaultDevice(),
      let queue = gpu.makeCommandQueue() else { fatalError("No Metal device") }
let source = """
#include <metal_stdlib>
using namespace metal;
kernel void hintTest(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) {
    out[i] = i * 3u + 7u;
}
"""
let library = try gpu.makeLibrary(source: source, options: nil)
guard let fn = library.makeFunction(name: "hintTest") else { fatalError("No function") }
print("GPU=\(gpu.name), maxThreads=\(gpu.maxThreadsPerThreadgroup)")
for hint in [0,1,32,48,64,256,1024] {
    let desc = MTLComputePipelineDescriptor()
    desc.computeFunction=fn
    if hint>0 { desc.maxTotalThreadsPerThreadgroup=hint }
    do {
        let state=try gpu.makeComputePipelineState(descriptor: desc, options: [], reflection: nil)
        let n=128
        guard let output=gpu.makeBuffer(length:n*4, options:.storageModeShared),
              let command=queue.makeCommandBuffer(),
              let enc=command.makeComputeCommandEncoder() else { fatalError("Allocation failure") }
        enc.setComputePipelineState(state)
        enc.setBuffer(output, offset:0, index:0)
        let width=max(1,min(state.maxTotalThreadsPerThreadgroup, hint>0 ? hint : 32,32))
        enc.dispatchThreads(MTLSize(width:n,height:1,depth:1),threadsPerThreadgroup:MTLSize(width:width,height:1,depth:1))
        enc.endEncoding()
        command.commit()
        command.waitUntilCompleted()
        let a=output.contents().bindMemory(to:UInt32.self,capacity:n)
        let good=command.status == .completed && (0..<n).allSatisfy{a[$0]==UInt32($0*3+7)}
        print("hint=\(hint) pipeline=PASS output=\(good ? "PASS":"FAIL") max=\(state.maxTotalThreadsPerThreadgroup)")
    } catch {
        print("hint=\(hint) pipeline=FAIL error=\(error)")
    }
    fflush(stdout)
}
