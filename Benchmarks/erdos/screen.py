"""Elaboration screen for imported Erdős problems (toolchain drift gate).

For each Problems/Erdos/p<n>/: assemble Defs.lean content + the
charter's ## Statement as `theorem main : <stmt> := by sorry` into one
scratch module and `lake env lean` it against THIS workspace's mathlib.
PASS → keep. FAIL → move the problem dir into Benchmarks/erdos/rejects/
(with the error head persisted alongside) so the corpus that reaches
`init-batch` is exactly the set that elaborates here.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WS = Path(r"D:/Asterism")
SCRATCH = WS / "_spike" / "erdos_screen"
REJECTS = WS / "Benchmarks" / "erdos" / "rejects"
CONCURRENCY = 3


def candidate(pdir: Path) -> "tuple[str, str] | None":
    seed = json.loads((pdir / "problem.json").read_text(encoding="utf-8"))
    m = re.search(r"## Statement\n([\s\S]*?)\n\n## ", seed["charter"])
    if not m:
        return None
    stmt = m.group(1).strip()
    defs = (pdir / "Defs.lean").read_text(encoding="utf-8")
    body = defs.replace(
        f"end Problems.Erdos.{pdir.name}",
        f"theorem main : {stmt} := by sorry\n\n"
        f"end Problems.Erdos.{pdir.name}")
    return seed["problem"], body


def screen_one(pdir: Path) -> "tuple[str, bool, float, str]":
    c = candidate(pdir)
    if c is None:
        return pdir.name, False, 0.0, "no ## Statement in charter"
    slug, body = c
    f = SCRATCH / f"{pdir.name}.lean"
    f.write_text(body, encoding="utf-8")
    t0 = time.time()
    try:
        r = subprocess.run(["lake", "env", "lean", str(f)], cwd=str(WS),
                           capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return pdir.name, False, time.time() - t0, "elaboration timeout 600s"
    dt = time.time() - t0
    if r.returncode == 0:
        return pdir.name, True, dt, ""
    err = (r.stdout + r.stderr).strip().splitlines()
    head = next((ln for ln in err if "error" in ln.lower()), err[0] if err else "?")
    return pdir.name, False, dt, head[:200]


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    REJECTS.mkdir(parents=True, exist_ok=True)
    dirs = sorted((WS / "Problems" / "Erdos").iterdir())
    results = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        for name, ok, dt, err in ex.map(screen_one, dirs):
            print(f"{'PASS' if ok else 'FAIL'} {name} {dt:5.1f}s {err}",
                  flush=True)
            results.append((name, ok, err))
    kept = [n for n, ok, _ in results if ok]
    for name, ok, err in results:
        if ok:
            continue
        dst = REJECTS / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(WS / "Problems" / "Erdos" / name), str(dst))
        (dst / "_reject_reason.txt").write_text(err + "\n", encoding="utf-8")
    print(f"\nkept {len(kept)}/{len(results)}; rejects in {REJECTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
