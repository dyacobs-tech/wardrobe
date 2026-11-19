#!/usr/bin/env python3
"""Run every test file against a local server of this checkout (CI and local).

    python3 tests/run_all.py [--only name ...]

Each test gets its own timeout. Files listed in QUARANTINE are run and
reported but cannot fail the run — each entry says why and what would
un-quarantine it. audit7x.py are screenshot audits (reports, not tests)
and sweep64.py is a visual sweep; they are not run here.
"""
from __future__ import annotations
import functools, http.server, os, socketserver, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TIMEOUT = int(os.environ.get("TEST_TIMEOUT", "300"))
SKIP = {"run_all.py", "buildinfo.py", "audit75.py", "audit76.py", "audit77.py", "audit78.py", "sweep64.py"}
QUARANTINE: dict[str, str] = {}
try:
    import json
    QUARANTINE = json.loads((HERE / "quarantine.json").read_text()).get("tests", {})
except Exception:
    pass


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    H = functools.partial(Quiet, directory=str(ROOT))
    socketserver.TCPServer.allow_reuse_address = True
    s = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}/"


def main():
    only = sys.argv[sys.argv.index("--only") + 1:] if "--only" in sys.argv else None
    files = sorted(f for f in os.listdir(HERE) if f.endswith(".py") and (f.startswith("test_") or f == "smoke.py") and f not in SKIP)
    if only:
        files = [f for f in files if any(o in f for o in only)]
    srv, base = serve()
    results = []
    for f in files:
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, str(HERE / f), base], cwd=ROOT, capture_output=True, text=True, timeout=TIMEOUT)
            code, out = p.returncode, (p.stdout + p.stderr)
        except subprocess.TimeoutExpired as e:
            code, out = "timeout", ((e.stdout or b"").decode(errors="ignore") if isinstance(e.stdout, bytes) else (e.stdout or ""))
        dt = time.time() - t0
        ok = code == 0
        q = f in QUARANTINE
        status = "PASS" if ok else ("QUARANTINED" if q else "FAIL")
        if ok and q:
            status = "PASS (quarantined — remove from quarantine.json)"
        results.append((f, status, dt))
        print(f"{status:12} {f}  ({dt:.0f}s)", flush=True)
        if not ok:
            tail = "\n".join([l for l in out.splitlines() if "FAIL" in l or "Error" in l][:15]) or out[-1500:]
            print("    " + tail.replace("\n", "\n    "), flush=True)
            if q:
                print("    quarantine reason: " + QUARANTINE[f], flush=True)
    srv.shutdown()
    fails = [r for r in results if r[1] == "FAIL"]
    print(f"\n{len(results)} files: {sum(r[1].startswith('PASS') for r in results)} pass, {len(fails)} fail, {sum(r[1] == 'QUARANTINED' for r in results)} quarantined")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
