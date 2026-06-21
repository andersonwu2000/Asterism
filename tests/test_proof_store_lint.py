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
        "proof_store.atomic_write / place_proof / remove_proof):\n"
        + "\n".join(offenders))


@pytest.mark.parametrize("name", _FILES)
def test_pipeline_imports_proof_store(name) -> None:
    text = (_PIPELINE / name).read_text(encoding="utf-8")
    assert "proof_store" in text, f"{name} should use state.proof_store"
