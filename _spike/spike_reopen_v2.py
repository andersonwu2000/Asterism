"""Followup: is same-URI reopen really 3s, or is worker still alive
because didClose hasn't fully terminated yet? Wait long after close
to confirm worker dead, then reopen.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
import psutil

sys.path.insert(0, ".")
from Tooling.lsp_client import LspClient


def lean_workers(parent_pid):
    try:
        p = psutil.Process(parent_pid)
    except psutil.NoSuchProcess:
        return []
    return [c for c in p.children(recursive=True)
            if "lean" in c.name().lower()]


def measure_open(c, path, content):
    t0 = time.perf_counter()
    c.did_open(path, content)
    uri = path.as_uri()
    try:
        c.wait_for_file_done(uri, timeout=120)
    except TimeoutError:
        pass
    c.wait_for_diagnostics_settled(uri, stable_for=3.0, max_wait=120.0)
    return time.perf_counter() - t0


def main():
    ws = Path("D:/Asterism")
    c = LspClient(ws)
    c.start()
    c.initialize(timeout=60)

    f = ws / "_spike_reopen2.lean"
    body = "import Mathlib\n\ntheorem foo : 1 + 1 = 2 := by rfl\n"
    f.write_text(body, encoding="utf-8")

    print(f"workers before: {len(lean_workers(c.proc.pid))}")
    t1 = measure_open(c, f, body)
    print(f"first didOpen: {t1:.1f}s, workers={len(lean_workers(c.proc.pid))}")

    c.notify("textDocument/didClose",
             {"textDocument": {"uri": f.as_uri()}})
    print(f"didClose sent. Waiting 30s...")
    time.sleep(30)
    print(f"workers 30s after didClose: {len(lean_workers(c.proc.pid))}")

    c.clear_diagnostics(f.as_uri())
    t2 = measure_open(c, f, body)
    print(f"second didOpen (30s after close, same URI): {t2:.1f}s")

    f.unlink(missing_ok=True)
    c.shutdown()


if __name__ == "__main__":
    main()
