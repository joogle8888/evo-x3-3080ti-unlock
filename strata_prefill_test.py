#!/usr/bin/env python3
# Strata prefill/decode test WITHOUT the vision encoder (own temp config, own port 8081, own log).
# Usage: python strata_prefill_test.py <label>      Starts the server, runs 4 fixed prompts, stops the server.
import json, os, random, re, subprocess, sys, time, urllib.request, pathlib, statistics, datetime
label = sys.argv[1]
S = pathlib.Path(os.environ.get("STRATA_DIR", r"C:\path\to\Strata"))
W = pathlib.Path(__file__).resolve().parent
cfg = json.loads((S / "strata-iq2_xs.json").read_text(encoding="utf-8"))
cfg.pop("vision", None)
cfg["port"] = 8081
cfg["log"] = str(W / f"strata-test-{label}.log")
cfgp = W / f"strata-test-{label}.json"
cfgp.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
words = [w for w in (S / "README.md").read_text(encoding="utf-8").replace("\n", " ").split() if w.isalpha()]
def prompt(seed, nwords):
    r = random.Random(seed)
    return "Fasse in einem Satz zusammen, worum es in diesem Text geht:\n\n" + " ".join(r.choice(words) for _ in range(nwords))
CASES = [("p8k", 11, 6000), ("p16k", 12, 12000), ("p16k_b", 13, 12000), ("p32k", 14, 24000)]
proc = subprocess.Popen([str(S / ".venv/Scripts/python.exe"), str(S / "serve/server.py"), "--engine", "strata", "--config", str(cfgp), "--port", "8081"],
                        cwd=str(S), stdout=open(W / f"strata-test-{label}.stdout", "w"), stderr=subprocess.STDOUT)
def api(path, body=None, timeout=600):
    req = urllib.request.Request("http://127.0.0.1:8081" + path, data=json.dumps(body).encode() if body else None, headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))
try:
    t0 = time.time()
    while time.time() - t0 < 900:
        try:
            if api("/v1/models", timeout=5)["data"][0]["status"]["value"] == "loaded":
                break
        except Exception:
            pass
        time.sleep(5)
    else:
        raise SystemExit("server did not become ready")
    print("ready after %.0f s" % (time.time() - t0), flush=True)
    rows = []
    for name, seed, nw in CASES:
        t = time.time()
        r = api("/v1/chat/completions", {"model": "qwen3.8-flash-next-iq2_xs", "messages": [{"role": "user", "content": prompt(seed, nw)}], "max_tokens": 200, "temperature": 0}, timeout=900)
        print(name, r["usage"], "%.1fs" % (time.time() - t), flush=True)
    time.sleep(2)
    for l in open(cfg["log"], encoding="utf-8", errors="ignore"):
        m = re.search(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms \(([\d.]+) tok/s\), (\d+) generated in (\d+) ms \(([\d.]+) tok/s\)", l)
        if m:
            rows.append({"prompt": int(m[1]), "reused": int(m[2]), "read": int(m[3]), "prefill_toks": float(m[5]), "gen": int(m[6]), "decode_toks": float(m[8])})
    print(json.dumps(rows, indent=1))
    (W / f"strata-prefill-result-{label}.json").write_text(json.dumps({"label": label, "time": datetime.datetime.now().isoformat(timespec="seconds"), "rows": rows}, indent=1))
finally:
    proc.terminate()
    time.sleep(3)
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "strata.exe"], capture_output=True)
