"""Structural lint: the pipeline commit paths must mutate proof artifacts ONLY
through `state.proof_store`, never via raw `write_text`/`unlink`/`shutil.copy` on
a proof-path variable. This is what keeps the DB↔file drift class eliminated by
construction — a future edit that reintroduces a scattered proof write trips
here. (attempts_dir scratch — patch.lean / new_*.lean / target — is exempt; it
is not a DB-tracked proof artifact.)"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_PIPELINE = _REPO / "Tooling" / "pipeline"

# Variables that hold a DB-tracked proof-artifact path (proofs/L_*.lean,
# _strategy_*.lean, the goal's own .lean). A raw mutation on any of these must
# go through proof_store instead. NOT listed: `new_path` / `new_ns` / `path` /
# `src` / `target` — those are attempts_dir scratch (`new_*.lean` slug-rename,
# the agent's working files), which are not DB-tracked proof artifacts.
_PROOF_VARS = ("dest", "scratch_dest", "goal_lean", "parent_abs")
_RAW_MUT_RE = re.compile(
    r"\b(" + "|".join(_PROOF_VARS) + r")\.(write_text|unlink)\s*\(")
_SHUTIL_RE = re.compile(r"shutil\.(copy2?|move)\s*\(")
# Pipeline code must reach `atomic_write` only through the OWNERSHIP-guarded
# wrappers (`place_proof` / `remove_proof`), never bare — a bare call skips the
# clobber guard and re-opens the clobber-then-orphan window. `atomic_write` is a
# proof_store-internal primitive; only proof_store.py may call it directly.
_BARE_ATOMIC_RE = re.compile(r"\batomic_write\s*\(")

_FILES = ["backward.py", "builder.py", "forward.py"]


@pytest.mark.parametrize("name", _FILES)
def test_no_raw_proof_mutation_in_pipeline(name) -> None:
    text = (_PIPELINE / name).read_text(encoding="utf-8")
    offenders = []
    for i, line in enumerate(text.splitlines(), 1):
        code = line.split("#", 1)[0]                 # ignore comments
        if _RAW_MUT_RE.search(code) or _SHUTIL_RE.search(code):
            offenders.append(f"{name}:{i}: {line.strip()}")
    assert not offenders, (
        "raw proof-file mutation outside proof_store (route it through "
        "proof_store.place_proof / remove_proof):\n"
        + "\n".join(offenders))


@pytest.mark.parametrize("name", _FILES)
def test_no_bare_atomic_write_in_pipeline(name) -> None:
    """Every proof-file write must carry the ownership guard. `place_proof`
    bundles `assert_writable` + `atomic_write`; a bare `atomic_write` skips the
    guard. Forbid it in pipeline code so a future write can't silently clobber a
    different goal's committed file (the gap that left forward.py's primary
    placement unguarded before this was wired in)."""
    text = (_PIPELINE / name).read_text(encoding="utf-8")
    offenders = []
    for i, line in enumerate(text.splitlines(), 1):
        code = line.split("#", 1)[0]                 # ignore comments
        if _BARE_ATOMIC_RE.search(code):
            offenders.append(f"{name}:{i}: {line.strip()}")
    assert not offenders, (
        "bare atomic_write in pipeline — route through the ownership-guarded "
        "proof_store.place_proof instead:\n" + "\n".join(offenders))


@pytest.mark.parametrize("name", _FILES)
def test_pipeline_imports_proof_store(name) -> None:
    text = (_PIPELINE / name).read_text(encoding="utf-8")
    assert "proof_store" in text, f"{name} should use state.proof_store"


# ---------------------------------------------------------------------
# Non-pipeline coverage (2026-07-03 mv_delta): the pipeline lint above is
# variable-name-based (dest/scratch_dest/…), which cannot see a glob-loop
# delete like recovery.py's `for f in …glob("L_*.lean"): f.unlink()`. Such
# a raw unlink bypasses proof_store's ownership guard + DB sync — the very
# "proved-file deleted, DB row left proved" drift the chokepoint prevents.
# Track vars bound from a proof-file glob (directly, or via a list built
# from one) and forbid a raw mutation on them in the state-mgmt files.
# ---------------------------------------------------------------------

_STATE = _REPO / "Tooling" / "state"
_CORE = _REPO / "Tooling" / "core"
_NONPIPELINE_FILES = [
    _STATE / "recovery.py",
    _CORE / "dispatcher.py",
    _REPO / "Tooling" / "quality" / "verify.py",
]
# a glob over DB-tracked proof artifacts
_PROOF_GLOB_RE = re.compile(r'glob\(\s*["\'](?:L_|_strategy_s|.*L_)\*?[^"\']*\.lean["\']')


def _proof_glob_vars(lines: "list[str]") -> "set[str]":
    """Vars that hold a proof-file path from a proof-glob: either bound
    directly (`x = ...glob("L_*.lean")...`), iterated (`for x in
    ...glob("L_*.lean")...`), or iterating a list built from one
    (`files = glob(...) + glob(...)` then `for x in files`)."""
    lists: set[str] = set()   # names holding a proof-file LIST
    proof_vars: set[str] = set()
    for ln in lines:
        code = ln.split("#", 1)[0]
        # x = <expr with a proof glob>  → x is a proof-file list/path
        m = re.match(r"\s*(\w+)\s*=\s*(.+)$", code)
        if m and _PROOF_GLOB_RE.search(m.group(2)):
            lists.add(m.group(1))
        # for x in <expr with a proof glob>  → x is a proof file
        m = re.match(r"\s*for\s+(\w+)\s+in\s+(.+):", code)
        if m and _PROOF_GLOB_RE.search(m.group(2)):
            proof_vars.add(m.group(1))
        # for x in <known proof-file list>  → x is a proof file
        if m:
            rhs = m.group(2).strip().rstrip(":").strip()
            if rhs in lists or (rhs.startswith("sorted(") and any(
                    li in rhs for li in lists)):
                proof_vars.add(m.group(1))
    return proof_vars


@pytest.mark.parametrize("path", _NONPIPELINE_FILES, ids=lambda p: p.name)
def test_no_raw_proof_glob_mutation_outside_pipeline(path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    pvars = _proof_glob_vars(lines)
    if not pvars:
        return
    mut = re.compile(r"\b(" + "|".join(re.escape(v) for v in pvars)
                     + r")\.(unlink|write_text)\s*\(")
    offenders = []
    for i, line in enumerate(lines, 1):
        code = line.split("#", 1)[0]
        if mut.search(code):
            offenders.append(f"{path.name}:{i}: {line.strip()}")
    assert not offenders, (
        "raw unlink/write_text on a proof-glob file outside proof_store "
        "(route through proof_store.remove_proof / place_proof):\n"
        + "\n".join(offenders))
