"""Lake-build helpers — shell out to `lake build` and parse rc.

Extracted from `pipeline/__init__.py`. Pure module: no DB,
no agent, no provider — depends only on subprocess + Path.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def lean_path_to_module(workspace: Path, lean_path: Path) -> str:
    """Convert workspace-relative .lean path to lean module name.
    Problems/wilson/Root.lean → Problems.wilson.Root
    Problems/wilson/proofs/L_x.lean → Problems.wilson.proofs.L_x
    """
    rel = lean_path.relative_to(workspace).with_suffix("")
    return ".".join(rel.parts)


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
    """
    try:
        r = subprocess.run(
            ["lake", "build", *modules],
            cwd=str(workspace),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=600,
        )
        out = (r.stdout + r.stderr).strip()
        ok = r.returncode == 0 and "error:" not in out.lower()
        return ok, out
    except subprocess.TimeoutExpired:
        return False, f"lake build {' '.join(modules)} timed out (600s)"


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
