# Runs Zagitta's generate_v67.py unchanged, except zstd decompression uses Python 3.14 compression.zstd
# (no external zstd binary). All SHA-256 checks in the original script stay active.
import sys, tarfile, importlib.util
from pathlib import Path
from compression import zstd
spec = importlib.util.spec_from_file_location("generate_v67", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def extract_member(package, name):
    with zstd.open(package, "rb") as z, tarfile.open(fileobj=z, mode="r|") as a:
        return m.read_member(a, name)
m.extract_member = extract_member
sys.argv = [sys.argv[1]] + sys.argv[2:]
raise SystemExit(m.main())
