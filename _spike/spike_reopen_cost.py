"""Measure the cost of didClose→didOpen on the same file via the same
backend. Does the second open share Mathlib's elaborated state with the
first, or pay a full re-elaborate?

Result determines whether file-level LRU eviction (Phase 2.5 plan) is
viable: if reopen is ~5-10s, eviction is cheap; if ~30s+, frequent
eviction would dominate spawn wall.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
from Tooling.lsp_client import LspClient


def measure_open(c: LspClient, path: Path, content: str) -> float:
    t0 = time.perf_counter()
    c.did_open(path, content)
    uri = path.as_uri()
    try:
        c.wait_for_file_done(uri, timeout=120)
    except TimeoutError:
        pass
    c.wait_for_diagnostics_settled(uri, stable_for=3.0, max_wait=120.0)
    return time.perf_counter() - t0


def main() -> None:
    ws = Path("D:/Asterism")
    c = LspClient(ws)
    c.start()
    c.initialize(timeout=60)

    smoke = ws / "_spike_reopen.lean"
    body = "import Mathlib\n\ntheorem foo : 1 + 1 = 2 := by rfl\n"
    smoke.write_text(body, encoding="utf-8")

    # First open: pays full cold cost (Mathlib first elaborate)
    t1 = measure_open(c, smoke, body)
    print(f"first didOpen → settled: {t1:.1f}s")

    c.notify("textDocument/didClose",
             {"textDocument": {"uri": smoke.as_uri()}})
    time.sleep(3)

    # Second open: same file, hopefully cheaper
    c.clear_diagnostics(smoke.as_uri())
    t2 = measure_open(c, smoke, body)
    print(f"second didOpen → settled: {t2:.1f}s")

    c.notify("textDocument/didClose",
             {"textDocument": {"uri": smoke.as_uri()}})
    time.sleep(3)

    # Third open with slightly different content (different file)
    body3 = body + "\ntheorem bar : 2 + 2 = 4 := by rfl\n"
    smoke3 = ws / "_spike_reopen3.lean"
    smoke3.write_text(body3, encoding="utf-8")
    t3 = measure_open(c, smoke3, body3)
    print(f"third didOpen (different file): {t3:.1f}s")

    smoke.unlink(missing_ok=True)
    smoke3.unlink(missing_ok=True)
    c.shutdown()


if __name__ == "__main__":
    main()
