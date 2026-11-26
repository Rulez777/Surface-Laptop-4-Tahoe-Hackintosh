# Tiger Lake Metal compute SWSB bounds fix (beta)

Rainy Window HDRP on Tahoe 26.7.1, i7-1185G7 / 8086:9A49, Unity 6000.3.24f1: two MTLCompilerService EXC_BAD_ACCESS reports at libigc-tgl.dylib+0x592d2a, vISA::SWSB::addGlobalDependence+778. Both RCX=128, RAX=0. Player log: XPC_ERROR_CONNECTION_INTERRUPTED after retries.

The local donor has no bounds guard before indexing LiveGRFBuckets. Its constructor records the actual bucket count at +0x28. The patch checks the count in the global dependency loop and in getLiveBucketsFromFootprint before calling add. Negative indices are rejected by unsigned comparison. No SWSB pass or valid dependency is bypassed.

Related upstream change: https://github.com/intel/intel-graphics-compiler/commit/8d90b91d8f15c54c432dee8ca2e55d5c6527b88c (DG2; not a full port). Exact donor and adapter hashes and all original instruction bytes are checked in install_hdrp_swsb_macos.py. The adapter's three embedded hash constants are updated, not disabled. No Apple binaries distributed. Both local libraries are signed and checked before replacement; backup and pair rollback provided.

Physical reference test: 2026-11-26 18:02 CET; new MTLCompilerService mapped both patched libraries, HDRP launched, no new compiler crash or GPU reset and no Player.log compile error in the observed run. Visual correctness, additional shaders and fresh-install testing remain open. This does not establish an FPS improvement.

Quick Start applies the fix after the existing graphics donor installation. For an existing compatible install: sudo python3 install_hdrp_swsb_macos.py apply ; restart. Rollback: sudo python3 install_hdrp_swsb_macos.py rollback ; restart. Close graphics applications before changing libraries. Unsupported hashes fail closed. No changes to SIP, kernel, EFI, power policy or game settings. No new diagnostic hooks or trace tools.
