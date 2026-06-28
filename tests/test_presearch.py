"""target-1 v1 pre-search (`Tooling/pipeline/_presearch.py`) unit tests.

Cover the framework-side verification + render + Context injection.
The agent spawn itself is exercised live, not here."""
from Tooling.pipeline import _presearch
from Tooling.agent import context


class _Info:
    def __init__(self, found, sig):
        self.found = found
        self.signature = sig


def test_verify_drops_hallucinated_mathlib(monkeypatch, tmp_path):
    """A Mathlib name that doesn't `#check` (found=False) is dropped."""
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(
        lemma_lookup, "lookup_batch",
        lambda names, ws: {"Real.add_comm": _Info(True, "sig"),
                           "Bogus.lemma": _Info(False, "")})
    cands = [{"name": "Real.add_comm", "source": "mathlib"},
             {"name": "Bogus.lemma", "source": "mathlib"}]
    names = [c["name"] for c in _presearch._verify(cands, tmp_path)]
    assert "Real.add_comm" in names
    assert "Bogus.lemma" not in names


def test_verify_keeps_when_lookup_unavailable(monkeypatch, tmp_path):
    """Offline / lake hiccup: keep Mathlib candidates unverified (best-effort)."""
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(
        lemma_lookup, "lookup_batch",
        lambda names, ws: (_ for _ in ()).throw(RuntimeError("offline")))
    assert _presearch._verify([{"name": "Real.add_comm", "source": "mathlib"}],
                              tmp_path)


def test_verify_library_against_index(tmp_path):
    """Library candidates are kept only when present in `Library/INDEX.md`."""
    (tmp_path / "Library").mkdir()
    (tmp_path / "Library" / "INDEX.md").write_text(
        "- `Library.X.real_thing`\n", encoding="utf-8")
    cands = [{"name": "Library.X.real_thing", "source": "library"},
             {"name": "Library.X.ghost", "source": "library"}]
    names = [c["name"] for c in _presearch._verify(cands, tmp_path)]
    assert "Library.X.real_thing" in names
    assert "Library.X.ghost" not in names


def test_section_present_when_cache_exists(tmp_path):
    """`_section_presearch_candidates` injects the cache when present, [] absent."""
    pdir = tmp_path / "Problems" / "p"
    (pdir / ".presearch").mkdir(parents=True)
    _presearch.presearch_path(pdir, 7).write_text(
        "## Candidate lemmas\n\n- `Foo.bar`\n", encoding="utf-8")
    out = context._section_presearch_candidates(pdir, 7)
    assert out and "Candidate lemmas" in "\n".join(out)
    assert context._section_presearch_candidates(pdir, 999) == []
