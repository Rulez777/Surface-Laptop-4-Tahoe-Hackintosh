#!/usr/bin/env python3
"""Strict read-only parser for Intel Tiger Lake DMC firmware v2.12.

The firmware itself is NOT redistributed or installed by this repository.
On SL4 the tool only audits a locally supplied public Intel firmware image
against a fixed SHA256 and validates each parser bound. No MMIO, EFI, EC,
OpenCore, kernel or power-state operations are performed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

FIRMWARE_SHA256 = "3c013ef0ad96ba73aee8e5bd04a8e27cc9b1c6e9183b1a83ce124485f325afca"
MAIN_SHA1 = "f2d9bebcd53a51abe92902770622cef2aed1ecc6"
MAIN_SIGNATURE = 0x40403e3e
FIRMWARE_LENGTH = 19760
FIRST_DWORD_MAIN = 0x0c004040
DMC_HEADER_DWORDS = 64
DMC_MMIO_ARRAY_LENGTH = 20
EXPECTED_MMIO = (0x8f074, 0x8f034, 0x8f004, 0x8f038, 0x8f008,
                 0x8f03c, 0x8f00c, 0x8f040, 0x8f010)


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def u32(data, offset):
    require(0 <= offset <= len(data)-4, "DMC structure truncated at "+str(offset))
    return struct.unpack_from("<I", data, offset)[0]


def parse(data, check_hash=True):
    require(len(data)==FIRMWARE_LENGTH, "Unexpected firmware length")
    actual=hashlib.sha256(data).hexdigest()
    if check_hash:
        require(actual==FIRMWARE_SHA256,"Firmware SHA256 differs from reviewed image")
    require(u32(data,0)==9, "Unexpected Intel CSS module type")
    css_len=u32(data,4)*4
    require(css_len==128, "Unexpected CSS header size")
    package_len=data[css_len]*4
    require(package_len==400, "Unexpected package header size")
    count=u32(data,css_len+12)
    require(count==2,"Unexpected DMC package count")
    package_end=css_len+package_len
    base0=package_end+u32(data,css_len+16+4)*4
    base1=package_end+u32(data,css_len+16+12+4)*4
    require(base0==528 and base1==18624,"Unexpected DMC header offsets")
    records=[]
    for idx,base in enumerate((base0,base1)):
        require(u32(data,base)==MAIN_SIGNATURE,"Bad DMC header signature")
        head_dw=data[base+4]
        version=data[base+5]
        require(head_dw==DMC_HEADER_DWORDS and version==3,"Unsupported DMC format")
        payload_dw=u32(data,base+12)
        address=u32(data,base+20)
        count=u32(data,base+92)
        require(0<count<=DMC_MMIO_ARRAY_LENGTH,"Invalid DMC MMIO count")
        require(address==(0x80000 if idx==0 else 0x90000),"Unexpected DMC load address")
        array_addr=base+96
        array_data=array_addr+DMC_MMIO_ARRAY_LENGTH*4  # fixed [20], not count-sized!
        addrs=struct.unpack_from("<"+str(count)+"I",data,array_addr)
        values=struct.unpack_from("<"+str(count)+"I",data,array_data)
        start=base+head_dw*4
        end=start+payload_dw*4
        require(end<=len(data),"DMC program truncated")
        program=data[start:end]
        records.append({
            "dmc_id":idx,"header_offset":base,"payload_start":start,"payload_end":end,
            "program_dwords":payload_dw,"load_address":address,
            "first_program_dword":u32(program,0),
            "mmio_writes":[{"address":f"0x{a:x}","value":f"0x{v:x}"} for a,v in zip(addrs,values)],
            "program_sha1":hashlib.sha1(program).hexdigest()
        })
    main,pipe=records
    require(main["program_dwords"]==4460, "Unexpected main DMC program size")
    require(main["payload_start"]==0x310 and main["payload_end"]==0x48c0,
            "Unexpected main DMC program boundaries")
    require(main["program_sha1"]==MAIN_SHA1,"Main DMC payload SHA1 mismatch")
    require(main["first_program_dword"]==FIRST_DWORD_MAIN,"Unexpected first DMC dword")
    require(len(main["mmio_writes"])==9,"Unexpected main MMIO write count")
    require(tuple(int(w["address"],16) for w in main["mmio_writes"])==EXPECTED_MMIO,
            "Unexpected main MMIO register list")
    # All correct MMIO v2.12 values are nonzero: the old example incorrectly
    # parsed them as zero when it used [mmio_count] rather than fixed [20].
    require(main["mmio_writes"][0]["value"]=="0x86fc0","Unexpected main DMC SSP base")
    require(main["mmio_writes"][1]["value"]=="0xc003b400",
            "DMC MMIO data array appears incorrectly positioned")
    require(pipe["program_dwords"]==220 and pipe["payload_end"]==len(data),
            "Unexpected pipe DMC program boundary")
    return {"firmware":"i915/tgl_dmc_ver2_12.bin",
            "firmware_bytes":len(data),"firmware_sha256":actual,
            "valid":True,"dmc":records,
            "software_only":True,"installed":False,
            "message":"Structural parsing only; no kernel patch or sleep/wake validated."}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("firmware",type=Path)
    p.add_argument("--json-out",type=Path)
    args=p.parse_args()
    result=parse(args.firmware.read_bytes())
    content=json.dumps(result,indent=2)+"\n"
    if args.json_out:
        require(not args.json_out.exists(),"Refuse to overwrite existing report")
        args.json_out.write_text(content,encoding="utf-8")
        print("DMC audit saved:",args.json_out)
    else:print(content,end="")


if __name__=="__main__":
    try:main()
    except (ValueError,OSError,struct.error) as e:
        print("STOP:",e,file=sys.stderr)
        sys.exit(1)
