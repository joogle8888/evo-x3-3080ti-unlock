# RTX 3080 Ti (10de:2208) unlock on GMK EVO-X3 via OCuLink - local changes and test scripts

Context: https://github.com/windows-GPU-UNLOCK/Windows-GPU-UNLOCK/issues/164

NOT included on purpose: the card's VBIOS dump (PROM.BIN) and the NVIDIA firmware files (NVIDIA licence, dump your own card / generate the assets yourself).

## Files
- `evo-x3-3080ti-local-changes.patch` - 8 changed lines on top of LightEssence/universal-windows-unlock-gpu (PR #153, commit e12e611): no auto-unlock after 30 s, Enter no longer unlocks, PCI command set to Memory-only (0x2, IO off) so the platform's PciIo BME enable gives 0x6 == original|4.
- `build-clang.py` - builds the fork with clang + lld-link (no w64devkit/GCC); any compile/link error is fatal; checks EFI subsystem, no imports, .reloc present.
- `run_generate_v67.py` - runs Zagitta's `firmware/generate_v67.py` unchanged but decompresses zstd with Python 3.14 `compression.zstd` (no zstd binary needed); its SHA-256 checks stay active.
- `gemm_bench.py` - cuBLAS GEMM benchmark via ctypes (FP32 pedantic, FP16/BF16/TF32 Tensor with FP32 accumulate).
- `strata_prefill_test.py` - prefill/decode test for the Strata engine (no vision encoder).
- `logs/` - RUN0002 (failed before touching the GPU), RUN0004 and RUN0005 (two cold-boot unlocks), benchmark JSONs.

## Results (RTX 3080 Ti, 4096x4096 GEMM, 30 samples, TFLOPS)
FP16 66.7 -> 109.4 / 111.3, BF16 67.2 -> 112.2 / 113.4, TF32 33.8 -> 56.0 / 56.8, FP32 pedantic 23.4 -> 23.1 / 23.4 (locked -> unlocked, two unlocked cold boots).
Strata (custom quantized kernels, PCIe-bound decode): no change.

## Safety
Unlock is RAM-only (no SPI/flash writes) and is lost at full shutdown. Boot 2 with the unpatched fork stopped before the firmware started. Not tested: sleep/hibernate, other GPUs, display output. `vendor/unlock_610.c` of the fork is heavily rewritten vs Zagitta's and was not fully audited. Use at your own risk; Secure Boot must be off.
