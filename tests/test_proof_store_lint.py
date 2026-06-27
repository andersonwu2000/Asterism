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
