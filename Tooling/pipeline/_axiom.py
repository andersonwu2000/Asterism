"""Axiom probe — single source of truth for "is this proof clean".

Runs `#print axioms <fq_name>` via a temp probe file that imports the
candidate's module, and verifies the axiom set is a subset of
`axioms_whitelist`. Returns (True, msg) iff clean.

THE invariant for `goals.status='proved'`: the DB row's status flips
to 'proved' iff `axiom_probe` returned ok on the goal's public name.
Every "mark proved" call site must run this and abort on failure.
Adding a new path that flips status without calling this is a
regression — `tests/test_axiom_invariant.py` enforces this.

Why lake build alone is insufficient: lake accepts files whose imports
contain `sorry`. The sorry'd module compiles fine; sorryAx propagates
through definitions to anything that uses them, but lake build returns
rc=0 throughout. Only `#print axioms` walks the dependency graph
through the kernel and reports every axiom touched.

Cost: ~5-15s per probe (lean startup + module load). Acceptable —
runs once per "mark proved" event, not in the dispatch hot path.
"""
from __future__ import annotations

import re
import subprocess
import uuid
from pathlib import Path

from ._lake import lean_path_to_module


_AXIOM_RE = re.compile(r"depends on axioms?\s*:\s*\[(.*?)\]", re.DOTALL)


def axiom_probe(
    workspace: Path,
    *,
    fq_name: str,
    module: str,
    whitelist: list[str],
    timeout: int = 180,
) -> tuple[bool, str]:
    """Run `#print axioms <fq_name>` and verify axiom set ⊆ whitelist.

    Returns:
      - (True, "axioms ok: [<sorted>]") on clean proof
      - (False, reason) otherwise. Reasons:
        * "no axioms_whitelist": Manifest didn't authorize bypass
        * "axiom probe failed: <exc>": probe couldn't run (timeout etc.)
        * "axiom probe rebuild rc=N": `lake build <module>` failed —
          source has compile error (rare: gateway.check_build said ok
          but lake disagreed; flag for investigation)
        * "axiom probe rc=N": lean rc != 0 (parse / import / kernel)
        * "rogue axioms: [<sorted>]": axioms used not in whitelist —
          almost always sorryAx, indicating transitive sorry import.

    Concurrent-safe: uuid-suffixed probe file avoids collision when
    pool=N callers run probes in parallel.
    """
    if not whitelist:
        return False, "no axioms_whitelist"

    # Rebuild olean from current source BEFORE probing. `lake env lean`
    # alone does NOT trigger rebuild — it uses whatever olean is on
    # disk, decided by mtime. Phase 2.5's `gateway.check_build` verify
    # path doesn't update olean (worker memory only), so a stale olean
    # from an earlier compilation (e.g. Phase 1 hint probe with `:= by
    # hint`, or from a prior PN run) can be served. Combined with
    # `shutil.copy2(patch, goal_lean)` preserving patch.lean's mtime,
    # `source.mtime < olean.mtime` is reachable → lake env lean reads
    # the stale olean → spurious sorryAx report.
    # `lake build` uses content hash, so it correctly rebuilds when
    # source has changed regardless of mtime ordering. If hash already
    # matches, this is a near-instant no-op.
    # See task #71 (cs_cancel false-positive on 2026-05-08).
    try:
        rb = subprocess.run(
            ["lake", "build", module],
            cwd=str(workspace), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, f"axiom probe failed: {exc}"
    if rb.returncode != 0:
        # If gateway.check_build said ok but lake build now fails, the
        # worker's elaborated state diverged from disk — likely a race
        # or worker bug. Surface stderr to aid diagnosis.
        tail = (rb.stderr or rb.stdout or "")[-400:].strip()
        return False, f"axiom probe rebuild rc={rb.returncode}: {tail}"

    probe = workspace / f"_axiom_probe_{uuid.uuid4().hex[:8]}.lean"
    probe.write_text(
        f"import {module}\n#print axioms {fq_name}\n",
        encoding="utf-8",
    )
    try:
        r = subprocess.run(
            ["lake", "env", "lean", str(probe)],
            cwd=str(workspace), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, f"axiom probe failed: {exc}"
    finally:
        probe.unlink(missing_ok=True)
    if r.returncode != 0:
        return False, f"axiom probe rc={r.returncode}"
    used: set[str] = set()
    m = _AXIOM_RE.search(r.stdout)
    if m:
        for a in m.group(1).split(","):
            a = a.strip()
            if a:
                used.add(a)
    rogue = used - set(whitelist)
    if rogue:
        return False, f"rogue axioms: {sorted(rogue)}"
    return True, f"axioms ok: {sorted(used) or '[]'}"


def axiom_probe_file(
    workspace: Path, dest: Path, *,
    problem: str, slug: str, whitelist: list[str],
) -> tuple[bool, str]:
    """Convenience wrapper: derive (fq_name, module) from a goal lean
    file + slug, then call `axiom_probe`. The standard call shape for
    Builder / verify_strategy / sub-goal-stub promotion."""
    fq_name = f"Problems.{problem}.{slug}"
    module = lean_path_to_module(workspace, dest)
    return axiom_probe(workspace, fq_name=fq_name, module=module,
                       whitelist=whitelist)
