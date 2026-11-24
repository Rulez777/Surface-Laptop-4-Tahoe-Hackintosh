import Foundation
import Metal
guard let gpu=MTLCreateSystemDefaultDevice() else {fatalError("No GPU")}
let lib=try gpu.makeLibrary(source:"""
#include <metal_stdlib>
using namespace metal;
vertex float4 v(uint i [[vertex_id]]) { const float2 p[3]={{-1,-1},{3,-1},{-1,3}}; return float4(p[i],0,1); }
fragment float4 f(float4 p [[position]]) { return float4(fract(p.x/31.0),fract(p.y/29.0),0.5,1); }
""",options:nil)
let desc=MTLRenderPipelineDescriptor()
desc.vertexFunction=lib.makeFunction(name:"v")
desc.fragmentFunction=lib.makeFunction(name:"f")
desc.colorAttachments[0].pixelFormat = .bgra8Unorm
let ps=try gpu.makeRenderPipelineState(descriptor:desc)
let queues=(0..<4).map{_ in gpu.makeCommandQueue()!}
let size=512
let td=MTLTextureDescriptor.texture2DDescriptor(pixelFormat:.bgra8Unorm,width:size,height:size,mipmapped:false)
td.storageMode = .private; td.usage = .renderTarget
let textures=(0..<8).map{_ in gpu.makeTexture(descriptor:td)!}
func run(_ depth:Int,_ count:Int) {
    let start=ProcessInfo.processInfo.systemUptime
    var pending:[MTLCommandBuffer]=[]
    var completed=0
    var gpuSeconds=0.0
    func finish(_ c:MTLCommandBuffer) {
        c.waitUntilCompleted()
        guard c.status == .completed else {fatalError("GPU failure: \(String(describing:c.error))")}
        completed += 1
        if c.gpuEndTime>c.gpuStartTime {gpuSeconds += c.gpuEndTime-c.gpuStartTime}
    }
    for i in 0..<count {
        if pending.count==depth {finish(pending.removeFirst())}
        let pass=MTLRenderPassDescriptor()
        pass.colorAttachments[0].texture=textures[i%depth]
        pass.colorAttachments[0].loadAction = .clear
        pass.colorAttachments[0].storeAction = .store
        let c=queues[i%queues.count].makeCommandBuffer()!
        let e=c.makeRenderCommandEncoder(descriptor:pass)!
        e.setRenderPipelineState(ps)
        e.drawPrimitives(type:.triangle,vertexStart:0,vertexCount:3)
        e.endEncoding(); c.commit(); pending.append(c)
    }
    for c in pending {finish(c)}
    let dt=ProcessInfo.processInfo.systemUptime-start
    print("depth=\(depth) completed=\(completed) wall_s=\(dt) buffers_per_sec=\(Double(completed)/dt) summed_gpu_s=\(gpuSeconds)")
    fflush(stdout)
}
run(1,100)
for _ in 0..<3 {for depth in [1,2,4,8] {run(depth,600)}}
