#!/usr/bin/env python3
# cuBLAS GEMM throughput via ctypes (no install): FP32 pedantic, FP16/BF16/TF32 tensor with FP32 accumulate.
# Mirrors the Windows-GPU-UNLOCK benchmark modes. Usage: python gemm_bench.py <label> [N] [samples]
import ctypes as C, os, sys, time, json, statistics, struct, subprocess, datetime
label = sys.argv[1] if len(sys.argv) > 1 else "run"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 4096
SAMPLES = int(sys.argv[3]) if len(sys.argv) > 3 else 30
base = os.environ.get("NVIDIA_PIP_DIR", r"C:\path\to\venv\Lib\site-packages\nvidia")  # pip: nvidia-cuda-runtime-cu12, nvidia-cublas-cu12
for d in ("cuda_runtime", "cublas"):
    os.add_dll_directory(os.path.join(base, d, "bin"))
rt = C.CDLL(os.path.join(base, "cuda_runtime", "bin", "cudart64_12.dll"))
bl = C.CDLL(os.path.join(base, "cublas", "bin", "cublas64_12.dll"))

def chk(r, what):
    if r != 0:
        raise SystemExit(f"{what} failed: {r}")

chk(rt.cudaSetDevice(0), "cudaSetDevice")
h = C.c_void_p()
chk(bl.cublasCreate_v2(C.byref(h)), "cublasCreate")
R16F, R16BF, R32F = 2, 14, 0
C32, C32_PED, C32_TF32 = 68, 69, 77
MODES = [  # name, in type, out type, compute type, bytes per element in
    ("fp32_pedantic", R32F, R32F, C32_PED, 4),
    ("fp16_tensor_fp32_accumulate", R16F, R32F, C32, 2),
    ("bf16_tensor_fp32_accumulate", R16BF, R32F, C32, 2),
    ("tf32_tensor_fp32_accumulate", R32F, R32F, C32_TF32, 4),
]

def alloc(nbytes):
    p = C.c_void_p()
    chk(rt.cudaMalloc(C.byref(p), C.c_size_t(nbytes)), "cudaMalloc")
    return p

def fill(p, nbytes, pattern):  # fill device buffer with repeating small values (no NaN/Inf)
    buf = (pattern * (nbytes // len(pattern) + 1))[:nbytes]
    chk(rt.cudaMemcpy(p, buf, C.c_size_t(nbytes), 1), "cudaMemcpy")

def pat(kind):
    import random
    random.seed(1)
    vals = [random.uniform(-0.5, 0.5) for _ in range(997)]
    if kind == R32F:
        return b"".join(struct.pack("<f", v) for v in vals)
    if kind == R16F:
        return b"".join(struct.pack("<e", v) for v in vals)
    return b"".join(struct.pack("<f", v)[2:] for v in vals)  # bf16 = top 16 bits of fp32

def gpu_info():
    q = "name,driver_version,pci.bus_id,power.limit,clocks.max.sm,clocks.max.mem,temperature.gpu"
    return subprocess.run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()

out = {"label": label, "time": datetime.datetime.now().isoformat(timespec="seconds"), "N": N, "gpu": gpu_info(), "modes": {}}
print(label, "N=%d" % N, out["gpu"])
ev0, ev1 = C.c_void_p(), C.c_void_p()
rt.cudaEventCreate(C.byref(ev0)); rt.cudaEventCreate(C.byref(ev1))
for name, tin, tout, comp, bpe in MODES:
    A, B, Cm = alloc(N * N * bpe), alloc(N * N * bpe), alloc(N * N * 4)
    p = pat(tin)
    fill(A, N * N * bpe, p); fill(B, N * N * bpe, p[::-1] if False else p)
    chk(rt.cudaMemset(Cm, 0, C.c_size_t(N * N * 4)), "memset")
    alpha, beta = C.c_float(1.0), C.c_float(0.0)

    def gemm():
        r = bl.cublasGemmEx(h, 0, 0, N, N, N, C.byref(alpha), A, tin, N, B, tin, N, C.byref(beta), Cm, tout, N, comp, -1)
        chk(r, "cublasGemmEx " + name)

    t_end = time.time() + 2.0
    while time.time() < t_end:  # warmup 2 s
        gemm()
    rt.cudaDeviceSynchronize()
    reps = 20
    res = []
    for _ in range(SAMPLES):
        rt.cudaEventRecord(ev0, None)
        for _ in range(reps):
            gemm()
        rt.cudaEventRecord(ev1, None)
        rt.cudaEventSynchronize(ev1)
        ms = C.c_float()
        rt.cudaEventElapsedTime(C.byref(ms), ev0, ev1)
        res.append(2.0 * N ** 3 * reps / (ms.value / 1000.0) / 1e12)
    out["modes"][name] = {"median_tflops": round(statistics.median(res), 2), "min": round(min(res), 2), "max": round(max(res), 2)}
    print(f"{name:30s} median {statistics.median(res):7.2f} TFLOPS  (min {min(res):.2f} max {max(res):.2f})")
    for x in (A, B, Cm):
        rt.cudaFree(x)
out["gpu_after"] = gpu_info()
fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"gemm-result-{label}.json")
json.dump(out, open(fn, "w"), indent=1)
print("saved", fn)
