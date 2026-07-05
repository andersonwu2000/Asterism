"""Problems/ artifact-lifecycle hygiene (task #9, user call 2026-07-05).

The rule: under Problems/, git tracks ONLY the three human input files
(Manifest.md / Defs.lean / Root.lean — plus the top-level README).
Everything generated is runtime state — proofs/ pairs with DB rows and
churns on resets/relabels, TREE/BRIEF are regenerated views, LESSONS'
knowledge lives in kb_entries, .drafts/.presearch are cross-spawn
scratch. Before this rule the tracking was bimodal (Minif2f fully
committed, the research-level problems fully untracked) and git status
carried 900+ lines of generated-file noise.

Proved EVIDENCE lives elsewhere by design: Library/ (curated harvest)
+ Benchmarks/proved_manifest.jsonl (task #8).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_ALLOWED_NAMES = {"Manifest.md", "Defs.lean", "Root.lean"}
_ALLOWED_EXACT = {"Problems/README.md"}


def _tracked_problem_files() -> "list[str]":
    r = subprocess.run(["git", "ls-files", "--cached", "Problems"],
                       capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:      # not a git checkout (sdist etc.) — nothing to check
        return []
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def test_only_input_files_tracked_under_problems():
    bad = [
        f for f in _tracked_problem_files()
        if f not in _ALLOWED_EXACT
        and f.rsplit("/", 1)[-1] not in _ALLOWED_NAMES
    ]
    assert not bad, (
        f"{len(bad)} generated/unexpected file(s) tracked under Problems/ "
        f"(first few: {bad[:5]}) — Problems/ tracks ONLY "
        "Manifest.md/Defs.lean/Root.lean; proved evidence belongs in "
        "Library/ + Benchmarks/proved_manifest.jsonl (see module docstring)")


def test_gitignore_covers_generated_artifacts():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pat in ("Problems/**/proofs/", "Problems/**/TREE.md",
                "Problems/**/BRIEF.md", "Problems/**/LESSONS.md",
                "Problems/**/.drafts/", "Problems/**/.presearch/"):
        assert pat in text, f".gitignore lost the {pat!r} rule"
