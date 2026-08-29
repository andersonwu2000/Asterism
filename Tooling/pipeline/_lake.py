"""Lake-build helpers — shell out to `lake build` and parse rc.

Extracted from `pipeline/__init__.py`. Pure module: no DB,
no agent, no provider — depends only on subprocess + Path.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..core.process_group import no_window_creationflags


def lean_path_to_module(workspace: Path, lean_path: Path) -> str:
    """Convert workspace-relative .lean path to lean module name.
    Problems/wilson/Root.lean → Problems.wilson.Root
    Problems/wilson/proofs/L_x.lean → Problems.wilson.proofs.L_x
    """
    rel = lean_path.relative_to(workspace).with_suffix("")
    return ".".join(rel.parts)


#: Upper bound on the joined `lake build <modules...>` command line per
#: subprocess call. Windows CreateProcess rejects command lines over
#: 32,767 chars with WinError 206 ("filename or extension too long");
#: 2026-08-29 the dedupe pre-flight passed a few hundred union_closed
#: proof modules (4,206 on disk, ~69 chars each, max 118) in ONE call,
#: tripped the limit, and — because the pre-flight is best-effort — the
#: whole defeq probe silently fail-opened (all 9,696 pairs refused,
#: alias=0) for days. The budget is deliberately far below the OS limit
#: so `lake`'s own argv handling never becomes the next ceiling; POSIX
#: ARG_MAX is much larger, but one shape everywhere keeps the test honest.
LAKE_CMDLINE_BUDGET = 8000


def chunk_modules_for_cmdline(modules: list[str],
                              budget: int = LAKE_CMDLINE_BUDGET
                              ) -> list[list[str]]:
    """Split `modules` into consecutive chunks whose joined argv
    (`lake build m1 m2 ...`, space-separated) stays within `budget`
    chars. Order is preserved; every module lands in exactly one chunk;
    a single module longer than the budget still gets its own chunk
    (lake, not us, decides whether that name is buildable)."""
    base = len("lake build")
    chunks: list[list[str]] = []
    cur: list[str] = []
    cur_len = base
    for m in modules:
        add = len(m) + 1
        if cur and cur_len + add > budget:
            chunks.append(cur)
            cur, cur_len = [], base
        cur.append(m)
        cur_len += add
    if cur:
        chunks.append(cur)
    return chunks


def lake_build_modules(workspace: Path,
                       modules: list[str]) -> tuple[bool, str]:
    """Run `lake build <m1> <m2> ...` for one or many module names.

    Lake's internal scheduler resolves the dependency DAG and builds
    independent modules in parallel. Passing N modules in a single
    call is therefore much faster than N sequential single-target
    invocations whenever any of those modules can run in parallel
    (e.g. Backward writes 4 sibling sub-goal files plus 1 strategy
    file that imports them all — sub-goals build concurrently, then
    the strategy serially).

    Long module lists are split into command-line-sized chunks
    (`LAKE_CMDLINE_BUDGET`, see the WinError 206 note above); the
    result is the conjunction of the chunk results with outputs
    joined. An empty `modules` keeps the historical shape — one bare
    `lake build` (the workspace default target) — rather than a silent
    no-op; callers guard the empty case themselves.
    """
    chunks = chunk_modules_for_cmdline(modules) if modules else [[]]
    ok_all = True
    outs: list[str] = []
    for chunk in chunks:
        try:
            r = subprocess.run(
                ["lake", "build", *chunk],
                cwd=str(workspace),
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=600,
                creationflags=no_window_creationflags(),
            )
        except subprocess.TimeoutExpired:
            return False, f"lake build {' '.join(chunk)} timed out (600s)"
        out = (r.stdout + r.stderr).strip()
        if out:
            outs.append(out)
        if not (r.returncode == 0 and "error:" not in out.lower()):
            ok_all = False
    return ok_all, "\n".join(outs)


def lake_build(workspace: Path, target_lean: Path) -> tuple[bool, str]:
    """Build a single .lean file's module (resolves deps).

    Thin wrapper around `lake_build_modules` — kept for Builder /
    Verify call sites that only ever build one target at a time.
    """
    module = lean_path_to_module(workspace, target_lean)
    return lake_build_modules(workspace, [module])


def lake_build_batch(workspace: Path,
                     targets: list[Path]) -> tuple[bool, str]:
    """Build multiple .lean files in one lake invocation. Lake
    parallelizes independent targets internally."""
    modules = [lean_path_to_module(workspace, t) for t in targets]
    return lake_build_modules(workspace, modules)
