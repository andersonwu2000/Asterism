"""PutnamBench Phase 1 prep driver: stratified 50-problem batch.

Selects 50 problems (12 strata A1..B6: 4 each + 1 extra for A1/B1),
emits Problem dirs via the adapter, validates that every statement
elaborates on THIS workspace's toolchain (upstream pins an older
Lean/Mathlib) with a single parallel `lake build`, substitutes
incompatible problems deterministically from the same stratum, then
registers the survivors with `init_problem` (its per-file build gate
hits the lake cache). Writes `phase1_selection.json` +
`phase1_report.md` next to this script.

Benchmark integrity: statements are NEVER edited — incompatible
problems are excluded and logged, substitutes come from the same
stratum in deterministic year order.

Usage (from the workspace root):
    python Benchmarks/putnambench/prepare_phase1.py [--dry-run]

The proving run itself is fired separately by the operator:
    asterism run --scope 'Putnam.%'
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "_ext" / "putnambench" / "lean4" / "src"
HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(WORKSPACE))          # Tooling imports
_spec = importlib.util.spec_from_file_location(
    "putnam_adapter", HERE / "adapter.py")
adapter = importlib.util.module_from_spec(_spec)
sys.modules["putnam_adapter"] = adapter
_spec.loader.exec_module(adapter)

STRATA = [f"{letter}{n}" for letter in "ab" for n in range(1, 7)]
PER_STRATUM = {s: (5 if s in ("a1", "b1") else 4) for s in STRATA}  # = 50
MAX_ROUNDS = 12


def upstream_commit() -> str:
    out = subprocess.run(
        ["git", "-C", str(SOURCE.parents[1]), "rev-parse", "--short",
         "HEAD"],
        capture_output=True, text=True, encoding="utf-8")
    return out.stdout.strip() if out.returncode == 0 else ""


def stratify() -> "OrderedDict[str, list[str]]":
    """Stratum → problem names sorted by year (deterministic)."""
    strata: OrderedDict[str, list[str]] = OrderedDict(
        (s, []) for s in STRATA)
    for p in sorted(SOURCE.glob("*.lean")):
        m = re.fullmatch(r"putnam_(\d{4})_([ab][1-6])", p.stem)
        if m:
            strata[m.group(2)].append(p.stem)
    return strata


def initial_targets(pool: list[str], k: int) -> list[int]:
    """k evenly-spaced indices across the year-sorted pool (full
    1962→2025 spread per stratum)."""
    n = len(pool)
    if k >= n:
        return list(range(n))
    if k == 1:
        return [0]
    return sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})


class Selection:
    """Per-stratum pick state with deterministic substitution: a
    failed pick is replaced by the next unused index (cyclic walk)."""

    def __init__(self, pool: list[str], k: int) -> None:
        self.pool = pool
        self.used: set[int] = set(initial_targets(pool, k))
        self.excluded: set[int] = set()

    def current(self) -> list[str]:
        return [self.pool[i] for i in sorted(self.used - self.excluded)]

    def exclude_and_substitute(self, name: str) -> str | None:
        idx = self.pool.index(name)
        self.excluded.add(idx)
        j = (idx + 1) % len(self.pool)
        while j != idx:
            if j not in self.used and j not in self.excluded:
                self.used.add(j)
                return self.pool[j]
            j = (j + 1) % len(self.pool)
        return None  # stratum exhausted


_ERR_NAME_RE = re.compile(r"Problems[/\\]Putnam[/\\](putnam_\w+)[/\\]")
_ERR_MOD_RE = re.compile(r"Problems\.Putnam\.(putnam_\w+)\.")


def lake_build(names: list[str]) -> tuple[bool, set[str], str]:
    """One parallel lake build over every candidate Root module.
    Returns (all_ok, failed_names, raw_output)."""
    mods = [f"Problems.Putnam.{n}.Root" for n in names]
    proc = subprocess.run(
        ["lake", "build", *mods], cwd=str(WORKSPACE),
        capture_output=True, text=True, encoding="utf-8",
        errors="replace")
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode == 0:
        return True, set(), out
    failed: set[str] = set()
    for line in out.splitlines():
        low = line.lower()
        if "error" not in low:
            continue
        for rx in (_ERR_NAME_RE, _ERR_MOD_RE):
            for m in rx.finditer(line):
                failed.add(m.group(1))
    return False, failed, out


def error_snippet(out: str, name: str, limit: int = 3) -> list[str]:
    hits = []
    for line in out.splitlines():
        if "error" in line.lower() and name in line:
            hits.append(line.strip()[:200])
            if len(hits) >= limit:
                break
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="print the initial selection and exit")
    args = ap.parse_args(argv)

    if not SOURCE.is_dir():
        print(f"FAIL: upstream clone missing at {SOURCE}\n"
              f"  git clone --depth 1 "
              f"https://github.com/trishullab/PutnamBench "
              f"_ext/putnambench", file=sys.stderr)
        return 1
    commit = upstream_commit()
    strata = stratify()
    sel = {s: Selection(pool, PER_STRATUM[s])
           for s, pool in strata.items()}

    def all_current() -> list[str]:
        return [n for s in STRATA for n in sel[s].current()]

    if args.dry_run:
        for s in STRATA:
            print(f"{s}: {', '.join(sel[s].current())}")
        print(f"total: {len(all_current())}")
        return 0

    excluded_log: list[dict] = []   # {name, stage, errors}
    specs: dict[str, "adapter.ProblemSpec"] = {}

    def emit(name: str) -> None:
        spec = adapter.parse_problem_file(SOURCE / f"{name}.lean")
        adapter.emit_problem_dir(spec, WORKSPACE / "Problems",
                                 upstream_commit=commit)
        specs[name] = spec

    def drop(name: str, stage: str, errors: list[str]) -> str | None:
        """Exclude `name`, clean its dir, return the substitute (also
        emitted) or None."""
        excluded_log.append(
            {"name": name, "stage": stage, "errors": errors})
        shutil.rmtree(WORKSPACE / "Problems" / "Putnam" / name,
                      ignore_errors=True)
        stratum = re.fullmatch(r"putnam_\d{4}_([ab][1-6])", name).group(1)
        sub = sel[stratum].exclude_and_substitute(name)
        if sub is None:
            print(f"[prep] WARNING: stratum {stratum} exhausted; "
                  f"batch will run short", flush=True)
            return None
        print(f"[prep] {name} excluded ({stage}) → substitute {sub}",
              flush=True)
        emit(sub)
        return sub

    pending = all_current()
    for name in pending:
        emit(name)
    print(f"[prep] emitted {len(pending)} candidate dirs "
          f"(upstream @ {commit})", flush=True)

    # -- validate/substitute loop: each round batch-builds the pending
    # candidates, then registers survivors (init's per-file build gate
    # hits the lake cache). Any failure at either stage spawns a
    # same-stratum substitute into the next round.
    from Tooling.core.cli import init_problem
    registered: list[str] = []
    rnd = 0
    while pending:
        rnd += 1
        if rnd > MAX_ROUNDS:
            print("[prep] FAIL: substitution did not converge within "
                  f"{MAX_ROUNDS} rounds", file=sys.stderr)
            return 1
        print(f"[prep] round {rnd}: lake build over {len(pending)} "
              f"candidate(s) ...", flush=True)
        ok, failed, out = lake_build(pending)
        if not ok and not failed:
            print("[prep] FAIL: lake build failed but no per-problem "
                  "error could be attributed; aborting.\n"
                  + out[-3000:], file=sys.stderr)
            return 1
        subs: list[str] = []
        for name in sorted(failed):
            sub = drop(name, "lake_build", error_snippet(out, name))
            if sub is not None:
                subs.append(sub)
        for name in pending:
            if name in failed:
                continue
            rc, msg = init_problem(WORKSPACE, f"Putnam.{name}")
            if rc == 0:
                registered.append(name)
            else:
                sub = drop(name, "init", [msg.strip()[:400]])
                if sub is not None:
                    subs.append(sub)
        pending = subs

    # -- report ---------------------------------------------------------
    selection = []
    for s in STRATA:
        for n in sel[s].current():
            spec = specs[n]
            year = int(re.match(r"putnam_(\d{4})", n).group(1))
            selection.append({
                "problem": f"Putnam.{n}", "stratum": s, "year": year,
                "has_solution_abbrev": bool(spec.solution_name),
            })
    (HERE / "phase1_selection.json").write_text(
        json.dumps({"upstream_commit": commit, "selected": selection,
                    "excluded": excluded_log}, indent=2),
        encoding="utf-8")

    n_sol = sum(1 for e in selection if e["has_solution_abbrev"])
    lines = [
        "# PutnamBench Phase 1 — prepared batch",
        "",
        f"Upstream: trishullab/PutnamBench @ {commit} "
        f"(toolchain there: v4.27.0; ours: see lean-toolchain).",
        f"Selected: **{len(selection)}** problems "
        f"({n_sol} with official solution filled in Defs.lean, "
        f"{len(selection) - n_sol} pure proof).",
        f"Excluded for toolchain incompatibility: {len(excluded_log)} "
        f"(statements never edited — excluded, not fixed).",
        "",
        "| stratum | problems |",
        "|---|---|",
    ]
    for s in STRATA:
        lines.append(f"| {s.upper()} | "
                     + ", ".join(sel[s].current()) + " |")
    if excluded_log:
        lines += ["", "## Excluded", ""]
        for e in excluded_log:
            lines.append(f"- `{e['name']}` ({e['stage']})")
            for err in e["errors"]:
                lines.append(f"  - `{err}`")
    lines += [
        "",
        "## Firing the run (operator)",
        "",
        "```",
        "asterism run --scope 'Putnam.%'",
        "```",
        "",
        f"G0 gate (ROADMAP): ≥40% proved of {len(selection)} → "
        f"full 270-problem Phase 2.",
    ]
    (HERE / "phase1_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    print(f"[prep] done: {len(registered)} registered, "
          f"{len(excluded_log)} excluded. Report: "
          f"Benchmarks/putnambench/phase1_report.md", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
