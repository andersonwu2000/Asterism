"""Spike: does didClose actually terminate the lean worker?

Per Watchdog.lean:1275 handleDidClose → terminateFileWorker → send exit
notification. Worker should exit on receipt. Empirically Phase 1 saw
workers persist after didClose — verify whether that's a real issue
or my misreading of the process tree.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, ".")
from Tooling.lsp.client import LspClient


def list_lean_children(parent_pid: int) -> list[psutil.Process]:
    try:
        parent = psutil.Process(parent_pid)
    except psutil.NoSuchProcess:
        return []
    out = []
    for p in parent.children(recursive=True):
        try:
            if "lean" in p.name().lower():
                out.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return out


def show(label: str, parent_pid: int) -> None:
    procs = list_lean_children(parent_pid)
    print(f"\n[{label}] {len(procs)} lean processes")
    for p in procs:
        try:
            mem = p.memory_info().rss / (1024 * 1024)
            cmd = " ".join(p.cmdline())[:80]
            print(f"  pid={p.pid:6d} rss={mem:5.0f}MB  cmd={cmd}")
        except Exception as e:
            print(f"  pid={p.pid:6d} err={e}")


def main() -> None:
    ws = Path("D:/Asterism")
    c = LspClient(ws)
    c.start()
    print(f"lake serve pid={c.proc.pid}")
    c.initialize(timeout=60)
    show("after initialize", c.proc.pid)

    smoke = ws / "_spike_smoke.lean"
    smoke.write_text("import Mathlib\n", encoding="utf-8")
    c.did_open(smoke, "import Mathlib\n")
    print("waiting 60s for elaborate...")
    time.sleep(60)
    show("after 60s elaborate", c.proc.pid)

    print("\ndidClose now")
    c.notify("textDocument/didClose",
             {"textDocument": {"uri": smoke.as_uri()}})

    last = 0
    for d in (3, 10, 30, 60):
        time.sleep(d - last)
        last = d
        show(f"+{d}s after didClose", c.proc.pid)

    smoke.unlink(missing_ok=True)
    c.shutdown()


if __name__ == "__main__":
    main()
