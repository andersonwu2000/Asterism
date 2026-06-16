"""Watcher (stats.md) observer guards — keep the live dashboard honest.

The watcher is a strictly non-invasive observer: it only reads on-disk state /
the DB and never changes pipeline code for its own benefit. These tests pin two
things that have silently drifted before:

1. The cleanup sub-agent Context.md titles written by the librarian modules and
   `_CLEANUP_TITLES` in the watcher stay in sync, so each live worker shows a
   curated `cleanup:<stage>` label. A drifted/added stage otherwise degraded to
   the "spawning, ?" placeholder (3 stages — Naming + imports / PR-style polish
   / Final mathlib review — had done exactly that). A graceful fallback in
   `_lookup_spawn_info` keeps it off the placeholder regardless, but the curated
   label is what we want, and this test catches drift at CI instead of by eye.

2. `_lib_dep_layers` orders library files by their import DAG (foundational
   first) — the data behind the dependency-ordered library table.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_watcher():
    spec = importlib.util.spec_from_file_location(
        "_watcher_under_test", ROOT / "demo" / "watcher.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_watcher = _load_watcher()

# Cleanup header lines read `f"# <Title> — {problem} ..."` in the librarian
# source. Pull the literal title out of each so the test fails the moment a
# stage is renamed/added without updating the watcher's title map. The dash is
# the em-dash (U+2014) used in the headers.
_TITLE_RE = re.compile(r'"# (.+?) — \{problem\}')
_LIB_SRC = [
    ROOT / "Tooling" / "quality" / "librarian" / "dedup.py",
    *sorted((ROOT / "Tooling" / "quality" / "librarian" / "cleanup").glob("*.py")),
]


def _source_cleanup_titles() -> set[str]:
    titles: set[str] = set()
    for src in _LIB_SRC:
        if not src.exists():
            continue
        for m in _TITLE_RE.finditer(src.read_text(encoding="utf-8")):
            titles.add(m.group(1))
    return titles


def test_every_cleanup_stage_title_is_mapped() -> None:
    src_titles = _source_cleanup_titles()
    # Guard against a broken regex silently passing: the scan must find the
    # known anchor stages.
    assert {"dedup audit", "PR-style polish"} <= src_titles, (
        f"title scan looks broken — found only {sorted(src_titles)}")
    missing = sorted(src_titles - set(_watcher._CLEANUP_TITLES))
    assert not missing, (
        "cleanup stage title(s) missing from watcher._CLEANUP_TITLES — a live "
        "worker on these shows a generic fallback instead of a curated "
        f"cleanup:<stage>: {missing}. Add them to demo/watcher.py.")


def test_no_stale_mapped_titles() -> None:
    # Reverse drift: a mapped title no longer written by any stage is dead
    # weight (the bug that left "Variable extraction" / "Docstring polish"
    # behind after they were merged into PR-style polish).
    stale = sorted(set(_watcher._CLEANUP_TITLES) - _source_cleanup_titles())
    assert not stale, (
        f"watcher._CLEANUP_TITLES maps title(s) no stage writes any more: "
        f"{stale}. Remove them from demo/watcher.py.")


def test_lib_dep_layers_orders_by_imports(tmp_path, monkeypatch) -> None:
    # A imports B; B imports only Mathlib → B is layer 0, A is layer 1.
    base = tmp_path / "Library" / "X"
    base.mkdir(parents=True)
    (base / "B.lean").write_text(
        "import Mathlib\n\ntheorem b : True := trivial\n", encoding="utf-8")
    (base / "A.lean").write_text(
        "import Library.X.B\n\ntheorem a : True := trivial\n", encoding="utf-8")
    monkeypatch.setattr(_watcher, "WS", tmp_path)
    layers = _watcher._lib_dep_layers(["Library/X/A.lean", "Library/X/B.lean"])
    assert layers["Library/X/B.lean"] == 0
    assert layers["Library/X/A.lean"] == 1


def test_lib_dep_layers_tolerates_missing_file(tmp_path, monkeypatch) -> None:
    # An unreadable file must not crash the watcher tick — it just lands in the
    # current layer.
    monkeypatch.setattr(_watcher, "WS", tmp_path)
    layers = _watcher._lib_dep_layers(["Library/X/Gone.lean"])
    assert layers["Library/X/Gone.lean"] == 0
