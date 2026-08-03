"""#149 — pin truth at the search-tool boundary.

Loogle indexes live Mathlib; the project pins an older revision; two
substitute deliverables shipped on phantom lemmas. The fix annotates
every returned name with elaborator truth against the pin, cached per
(pin_rev, decl) so the gateway only sees misses.
"""
from __future__ import annotations

import io
import json
import sqlite3
import urllib.request
from pathlib import Path

import pytest

from Tooling.knowledge import loogle, pin_check

REV = "85e6e1b45ac3992b8b08b789e314e2b2adf4d5c5"


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "lake-manifest.json").write_text(json.dumps(
        {"packages": [{"name": "mathlib", "rev": REV}]}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _seed(root: Path, decl: str, present: bool) -> None:
    conn = pin_check._cache(root)
    conn.execute(
        "INSERT OR REPLACE INTO decl_pin VALUES (?,?,?,?)",
        (REV, decl, int(present), "2026-08-03T00:00:00Z"))
    conn.commit()
    conn.close()


def test_cache_hit_never_touches_the_gateway(root, monkeypatch):
    """(pin_rev, decl) is immutable while the pin stands — a cached
    verdict must not cost a borrow (each borrow evicts a warm slot)."""
    _seed(root, "Nat.add_comm", True)
    _seed(root, "Phantom.lemma", False)
    def boom(*a, **kw):
        raise AssertionError("gateway probed on a full cache hit")
    monkeypatch.setattr(pin_check, "_gateway_probe", boom)
    out = pin_check.check_names(["Nat.add_comm", "Phantom.lemma"])
    assert out == {"Nat.add_comm": True, "Phantom.lemma": False}


def test_misses_are_probed_once_and_cached(root, monkeypatch):
    calls: list[list[str]] = []
    def fake_probe(_root, names):
        calls.append(list(names))
        return {n: n == "Real.exp_pos" for n in names}
    monkeypatch.setattr(pin_check, "_gateway_probe", fake_probe)
    out = pin_check.check_names(["Real.exp_pos", "Gone.thm"])
    assert out == {"Real.exp_pos": True, "Gone.thm": False}
    assert calls == [["Real.exp_pos", "Gone.thm"]]
    # Second call: verdicts now come from the cache.
    monkeypatch.setattr(pin_check, "_gateway_probe",
                        lambda *a: pytest.fail("probed again"))
    assert pin_check.check_names(["Gone.thm"]) == {"Gone.thm": False}


def test_inconclusive_probe_yields_none_and_caches_nothing(root, monkeypatch):
    """Gateway down / import failure → unknown, never a false verdict,
    and nothing poisoned into the cache."""
    monkeypatch.setattr(pin_check, "_gateway_probe", lambda *a: None)
    assert pin_check.check_names(["X.y"]) == {"X.y": None}
    conn = sqlite3.connect(root / ".asterism" / "pin_decl_cache.db")
    assert conn.execute("SELECT COUNT(*) FROM decl_pin").fetchone()[0] == 0
    conn.close()


def test_no_manifest_means_unverified(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert pin_check.check_names(["A.b"]) == {"A.b": None}


def _fake_verify(diags):
    class _Resp(io.BytesIO):
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    def opener(req, timeout=0):
        return _Resp(json.dumps({"ok": not diags,
                                 "diagnostics": diags}).encode())
    return opener


def test_probe_maps_error_lines_to_names(root, monkeypatch):
    """Line 1 is the import; line i+2 is names[i]. `also_lines` from the
    gateway's repeat-collapse counts too."""
    monkeypatch.setattr(urllib.request, "urlopen", _fake_verify([
        {"line": 3, "severity": "error", "message": "unknown constant"},
        {"line": 4, "severity": "error", "message": "unknown constant",
         "also_lines": [5]},
        {"line": 2, "severity": "info", "message": "Nat.add_comm : ..."},
    ]))
    out = pin_check._gateway_probe(root, ["A.ok", "B.gone", "C.gone",
                                          "D.gone"])
    assert out == {"A.ok": True, "B.gone": False, "C.gone": False,
                   "D.gone": False}


def test_probe_import_failure_is_inconclusive(root, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _fake_verify([
        {"line": 1, "severity": "error", "message": "unknown module"},
    ]))
    assert pin_check._gateway_probe(root, ["A.b"]) is None


def test_loogle_output_carries_the_pin_labels(monkeypatch):
    """The agent-facing line format: every hit annotated; a NOT hit
    adds the teaching note (live index vs pin), and the wording never
    claims the mathematics is absent — only the name."""
    monkeypatch.setattr(pin_check, "check_names",
                        lambda names: {"Real.exp_pos": True,
                                       "Phantom.thm": False,
                                       "Odd.duck": None})
    text = loogle._format({"count": 3, "hits": [
        {"name": "Real.exp_pos", "type": ": 0 < x.exp", "module": "M"},
        {"name": "Phantom.thm", "type": ": True", "module": "M"},
        {"name": "Odd.duck", "type": ": True", "module": "M"},
    ]}, limit=15)
    assert "Real.exp_pos  ::  0 < x.exp  [M]  [in pin]" in text
    assert "[NOT in pin under this name — do not cite as-is]" in text
    assert "[pin: unverified]" in text
    assert "loogle indexes LIVE Mathlib" in text
