#!/usr/bin/env python3
# LOCAL build of the LightEssence fork with clang + lld-link (no w64devkit/GCC). Any compile or link
# error is fatal. Output: build-clang/BOOTX64.EFI. Usage: python build-clang.py
import hashlib, pathlib, struct, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent
BD = ROOT / "build-clang"
BD.mkdir(exist_ok=True)
CLANG = r"C:\Program Files\LLVM\bin\clang.exe"
LLD = r"C:\Program Files\LLVM\bin\lld-link.exe"
SOURCES = """src/format src/logger src/sha256 src/runtime src/compat src/port src/profile src/checks
src/asset_loader src/pci_scan src/vbios_loader src/vbios_parser src/display_release vendor/unlock_610
vendor/prep_610 vendor/layout_610 vendor/vbios_610 vendor/gfw_eval src/unlock_engine src/app""".split()
EDK = ROOT / "vendor" / "edk2" / "Include"
FLAGS = ["-target", "x86_64-pc-windows-msvc", "-std=c11", "-Os", "-Wall", "-Wextra",
         "-Wno-unused-parameter", "-Wno-misleading-indentation",
         "-D__KERNEL__", "-DGU_UEFI_PORT", "-DGU_AD104_TRANSACTION", "-DGU_ENTRY_LATCHED_SS1_FULL",
         f"-I{ROOT}", f"-I{ROOT / 'include'}", f"-I{ROOT / 'compat'}", f"-I{EDK}", f"-I{EDK / 'X64'}",
         "-ffreestanding", "-fno-builtin", "-fno-stack-protector", "-mno-red-zone", "-fshort-wchar"]

objs = []
for s in SOURCES:
    o = BD / (s.replace("/", "_") + ".obj")
    r = subprocess.run([CLANG] + FLAGS + ["-c", str(ROOT / (s + ".c")), "-o", str(o)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    if r.returncode:
        print("COMPILE FAIL", s, r.stderr[:2000]); sys.exit(1)
    objs.append(str(o))
out = BD / "BOOTX64.EFI"
r = subprocess.run([LLD, "/nologo", "/nodefaultlib", "/subsystem:efi_application", "/entry:UefiMain",
                    "/machine:x64", "/base:0", "/dynamicbase", "/nxcompat", "/timestamp:0",
                    "/opt:ref", "/opt:icf", f"/map:{BD / 'UNLOCK.map'}", f"/out:{out}"] + objs,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
if r.returncode:
    print("LINK FAIL", r.stdout[:2000], r.stderr[:2000]); sys.exit(1)
d = out.read_bytes()
pe = struct.unpack_from("<I", d, 60)[0]
opt = pe + 24
subsys = struct.unpack_from("<H", d, opt + 68)[0]
imp = struct.unpack_from("<II", d, opt + 112 + 8)
rel = struct.unpack_from("<II", d, opt + 112 + 40)
assert subsys == 10 and imp == (0, 0) and rel[1] > 0, (subsys, imp, rel)
print(f"OK {len(d)} bytes sha256={hashlib.sha256(d).hexdigest()} subsystem={subsys} imports={imp} reloc={rel}")
