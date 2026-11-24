import Foundation
import Metal
guard let g=MTLCreateSystemDefaultDevice(),let q=g.makeCommandQueue() else {exit(3)}
let lib=try g.makeLibrary(source:"""
#include <metal_stdlib>
using namespace metal;
vertex float4 v(uint i [[vertex_id]]) {const float2 p[3]={{-1,-1},{3,-1},{-1,3}};return float4(p[i],0.5,1);}
fragment float4 f() {return float4(1);}
fragment float2 inspect(float4 pos [[position]], texture2d<float,access::read> color [[texture(0)]], depth2d<float> depth [[texture(1)]]) {
    uint2 p=uint2(pos.xy);
    constexpr sampler s(coord::pixel,filter::nearest);
    float a=color.read(p).r;
    float z=depth.sample(s,float2(p)+0.5);
    return float2(a,z);
}
""",options:nil)
let inspectDesc=MTLRenderPipelineDescriptor();inspectDesc.vertexFunction=lib.makeFunction(name:"v");inspectDesc.fragmentFunction=lib.makeFunction(name:"inspect");inspectDesc.colorAttachments[0].pixelFormat = .rg32Float
let inspectPipe=try g.makeRenderPipelineState(descriptor:inspectDesc)
let dd=MTLDepthStencilDescriptor();dd.depthCompareFunction = .less;dd.isDepthWriteEnabled=true
let ds=g.makeDepthStencilState(descriptor:dd)!
var failures=0,tests=0
for (w,h) in [(512,256),(1248,832)] {
 for fmt:MTLPixelFormat in [.r8Unorm] {
  let td=MTLTextureDescriptor.texture2DDescriptor(pixelFormat:fmt,width:w,height:h,mipmapped:false);td.storageMode = .private;td.usage=[.renderTarget,.shaderRead]
  let colorSize=g.heapTextureSizeAndAlign(descriptor:td)
  let dp=MTLTextureDescriptor.texture2DDescriptor(pixelFormat:.depth32Float,width:w,height:h,mipmapped:false);dp.storageMode = .private;dp.usage=[.renderTarget,.shaderRead]
  let depthSize=g.heapTextureSizeAndAlign(descriptor:dp)
  let hd=MTLHeapDescriptor();hd.storageMode = .private;hd.hazardTrackingMode = .tracked;hd.size=colorSize.size+depthSize.size+max(colorSize.align,depthSize.align)*2
  guard let heap=g.makeHeap(descriptor:hd) else {fatalError("No heap")}
  let p=MTLRenderPipelineDescriptor();p.vertexFunction=lib.makeFunction(name:"v");p.fragmentFunction=lib.makeFunction(name:"f");p.colorAttachments[0].pixelFormat=fmt;p.depthAttachmentPixelFormat = .depth32Float
  let pipe=try g.makeRenderPipelineState(descriptor:p)
  let out=g.makeBuffer(length:w*h*8,options:.storageModeShared)!
  let outputDesc=MTLTextureDescriptor.texture2DDescriptor(pixelFormat:.rg32Float,width:w,height:h,mipmapped:false);outputDesc.storageMode = .private;outputDesc.usage=[.renderTarget];let output=g.makeTexture(descriptor:outputDesc)!
  for i in 0..<4 {
   let colorHeap=CommandLine.arguments.contains("--color-heap"), depthHeap=CommandLine.arguments.contains("--depth-heap")
   guard let t=(colorHeap ? heap.makeTexture(descriptor:td) : g.makeTexture(descriptor:td)),let z=(depthHeap ? heap.makeTexture(descriptor:dp) : g.makeTexture(descriptor:dp)) else {fatalError("Allocation")}
   let c=q.makeCommandBuffer()!,r=MTLRenderPassDescriptor(),left=(i%2==0)
   r.colorAttachments[0].texture=t;r.colorAttachments[0].loadAction = .clear;r.colorAttachments[0].storeAction = .store;r.colorAttachments[0].clearColor=MTLClearColor(red:0,green:0,blue:0,alpha:0)
   r.depthAttachment.texture=z;r.depthAttachment.loadAction = .clear;r.depthAttachment.storeAction = .store;r.depthAttachment.clearDepth=1
   let e=c.makeRenderCommandEncoder(descriptor:r)!
   e.setRenderPipelineState(pipe);e.setDepthStencilState(ds);e.setScissorRect(MTLScissorRect(x:left ? 0:w/2,y:0,width:w/2,height:h));e.drawPrimitives(type:.triangle,vertexStart:0,vertexCount:3);e.endEncoding()
   let pr=MTLRenderPassDescriptor();pr.colorAttachments[0].texture=output;pr.colorAttachments[0].loadAction = .clear;pr.colorAttachments[0].storeAction = .store
   let f=c.makeRenderCommandEncoder(descriptor:pr)!;f.setRenderPipelineState(inspectPipe);f.setFragmentTexture(t,index:0);f.setFragmentTexture(z,index:1);f.drawPrimitives(type:.triangle,vertexStart:0,vertexCount:3);f.endEncoding()
   let bl=c.makeBlitCommandEncoder()!;bl.copy(from:output,sourceSlice:0,sourceLevel:0,sourceOrigin:MTLOrigin(x:0,y:0,z:0),sourceSize:MTLSize(width:w,height:h,depth:1),to:out,destinationOffset:0,destinationBytesPerRow:w*8,destinationBytesPerImage:w*h*8);bl.endEncoding()
   c.commit();let limit=ProcessInfo.processInfo.systemUptime+3
   while c.status != .completed && c.status != .error && ProcessInfo.processInfo.systemUptime<limit {Thread.sleep(forTimeInterval:0.001)}
   guard c.status == .completed else {print("COMMAND_FAILED \(c.status.rawValue) \(String(describing:c.error))");exit(3)}
   let a=out.contents().assumingMemoryBound(to:UInt32.self);var cb=0,zb=0
   for y in 0..<h {for x in 0..<w {let on=(x<w/2)==left, j=(y*w+x)*2;if a[j] != Float(on ? 1:0).bitPattern {cb+=1};if a[j+1] != Float(on ? 0.5:1).bitPattern {zb+=1}}}
   print("DETAIL frame=\(i) colorHeap=\(colorHeap) depthHeap=\(depthHeap) depthLeft=\(Float(bitPattern:a[1])) depthRight=\(Float(bitPattern:a[(w-1)*2+1])) colorLeft=\(Float(bitPattern:a[0])) colorRight=\(Float(bitPattern:a[(w-1)*2]))")
   if colorHeap {t.makeAliasable()};if depthHeap {z.makeAliasable()}
   tests+=1;if cb+zb>0{failures+=1;print("FAIL \(w)x\(h) fmt=\(fmt.rawValue) frame=\(i) color=\(cb) depth=\(zb)")}
  }
  print("FORMAT \(w)x\(h) \(fmt.rawValue) tests=\(tests) failures=\(failures)");fflush(stdout)
 }
}
print("RESULT tests=\(tests) failures=\(failures)")
exit(failures==0 ? 0:2)
