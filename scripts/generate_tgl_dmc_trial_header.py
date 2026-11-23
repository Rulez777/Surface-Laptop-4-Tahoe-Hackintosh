#!/usr/bin/env python3
"""Generate a LOCAL-ONLY, nonredistributable trial payload header.

Input: separately obtained and SHA256-pinned tgl_dmc_ver2_12.bin.
This operation neither loads the firmware nor changes the running kext/EFI.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import struct

APPROVED = Path(__file__).resolve().with_name("inspect_tgl_dmc.py")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("firmware",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    assert not a.out.exists(),"Refuse to overwrite header"
    spec=importlib.util.spec_from_file_location("dmc",APPROVED)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    binary=a.firmware.read_bytes()
    result=module.parse(binary)
    head=result["dmc"][0]
    payload=binary[head["payload_start"]:head["payload_end"]]
    words=struct.unpack("<4460I",payload)
    lines=['#pragma once','// Local-only reviewed Intel TGL DMC firmware payload v2.12.',
           '// Do not distribute header unless firmware redistribution rights are verified.',
           '// Firmware SHA256 '+result["firmware_sha256"],
           '// Payload SHA1 '+head["program_sha1"],
           '#include <stdint.h>',
           'namespace SL4TGLDMC {',
           'static const uint32_t kLoadAddress = 0x80000;',
           'static const uint32_t kProgramDwords = 4460;',
           'static const uint32_t kProgram[4460] = {']
    for start in range(0,len(words),8):
        lines.append('    '+', '.join('0x%08x'%v for v in words[start:start+8])+',')
    mmio=head["mmio_writes"]
    lines += ['};',
              'struct Write { uint32_t addr; uint32_t data; };',
              'static const uint32_t kMmioWriteCount = 9;',
              'static const Write kMmioWrites[9] = {']
    for w in mmio:
        lines.append('    {'+w["address"]+', '+w["value"]+'},')
    lines += ['};','} // namespace SL4TGLDMC']
    a.out.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('LOCAL header:',a.out,'words:',len(words),'sha256:',hashlib.sha256(a.out.read_bytes()).hexdigest())


if __name__=='__main__':main()
