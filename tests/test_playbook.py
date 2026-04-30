"""F22 — per-problem playbook: idiom extraction, curation, atomicity."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from Tooling import db, llm, playbook
from Tooling.playbook import (
    PLAYBOOK_CAP,
    CurationResult,
    _normalize_candidate,
    curate_and_write,
    extract_idiom,
    maybe_record_idiom,
    parse_entries,
    read_playbook,
)


# ---------------------------------------------------------------------
# parse_entries — playbook splitter
# ---------------------------------------------------------------------

def test_parse_entries_empty() -> None:
    assert parse_entries("") == []
    assert parse_entries("\n\n  \n") == []


def test_parse_entries_single_bullet() -> None:
    assert parse_entries("- **foo**: bar\n") == ["- **foo**: bar"]


def test_parse_entries_multiple_bullets_separated_by_blank() -> None:
    text = "- **a**: x\n\n- **b**: y\n"
    assert parse_entries(text) == ["- **a**: x", "- **b**: y"]


def test_parse_entries_multiline_bullet() -> None:
    """A bullet may span multiple lines until the next bullet."""
    text = (
        "- **a**: idiom line 1\n"
        "  continuation line 2\n"
        "\n"
        "- **b**: another\n"
    )
    entries = parse_entries(text)
    assert len(entries) == 2
    assert "continuation line 2" in entries[0]


# ---------------------------------------------------------------------
# _normalize_candidate
# ---------------------------------------------------------------------

def test_normalize_candidate_well_formed() -> None:
    raw = "- **ZMod val**: use ZMod.val_natCast with NeZero p instance"
    assert _normalize_candidate(raw) == raw


def test_normalize_candidate_skip_signal() -> None:
    assert _normalize_candidate("SKIP") is None


def test_normalize_candidate_empty_returns_none() -> None:
    assert _normalize_candidate("") is None
    assert _normalize_candidate("   \n  ") is None


def test_normalize_candidate_no_bullet_returns_none() -> None:
    """Reply must contain a bullet to count as a candidate."""
    assert _normalize_candidate("just some prose, no bullet here") is None


def test_normalize_candidate_extracts_bullet_from_preamble() -> None:
    """LLM may preamble before the bullet; first bullet wins."""
    raw = (
        "Here is the idiom:\n"
        "- **goal X**: do Y\n"
    )
    out = _normalize_candidate(raw)
    assert out == "- **goal X**: do Y"


def test_normalize_candidate_caps_at_three_lines() -> None:
    raw = (
        "- **a**: line1\n"
        "  continuation 2\n"
        "  continuation 3\n"
        "  this fourth line should be cut\n"
    )
    out = _normalize_candidate(raw)
    assert out is not None
    assert len(out.splitlines()) == 3
    assert "this fourth" not in out


# ---------------------------------------------------------------------
# read_playbook
# ---------------------------------------------------------------------

def test_read_playbook_missing_file(tmp_path: Path) -> None:
    assert read_playbook("p", tmp_path) == ""


def test_read_playbook_existing_file(tmp_path: Path) -> None:
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "playbook.md").write_text("- **a**: x\n", encoding="utf-8")
    assert "- **a**: x" in read_playbook("p", tmp_path)


# ---------------------------------------------------------------------
# curate_and_write — under cap (simple append)
# ---------------------------------------------------------------------

def _make_existing(tmp_path: Path, problem: str, n: int) -> Path:
    pdir = tmp_path / "Problems" / problem
    pdir.mkdir(parents=True, exist_ok=True)
    p = pdir / "playbook.md"
    entries = [f"- **goal{i}**: idiom{i}" for i in range(n)]
    p.write_text("\n\n".join(entries) + "\n", encoding="utf-8")
    return p


def test_curate_appends_when_under_cap(tmp_path: Path) -> None:
    _make_existing(tmp_path, "p", 3)
    cand = "- **new**: novel idiom"
    res = curate_and_write("p", cand, tmp_path)
    assert res.action == "appended"
    text = read_playbook("p", tmp_path)
    entries = parse_entries(text)
    assert len(entries) == 4
    assert entries[-1] == cand


def test_curate_creates_file_when_missing(tmp_path: Path) -> None:
    """No prior playbook.md and no Problems dir at all → create both."""
    cand = "- **first**: very first idiom"
    res = curate_and_write("brand_new", cand, tmp_path)
    assert res.action == "appended"
    p = tmp_path / "Problems" / "brand_new" / "playbook.md"
    assert p.exists()
    assert cand in p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------
# curate_and_write — at cap (LLM-driven self-curation)
# ---------------------------------------------------------------------

@pytest.fixture
def at_cap(tmp_path: Path) -> Path:
    """Playbook with PLAYBOOK_CAP entries."""
    return _make_existing(tmp_path, "p", PLAYBOOK_CAP)


def _stub_provider(reply: str | None) -> MagicMock:
    p = MagicMock()
    p.complete_text = MagicMock(return_value=reply)
    return p


def test_curate_at_cap_replace_evicts_chosen_entry(
    tmp_path: Path, at_cap: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm, "get_provider",
                        lambda: _stub_provider("REPLACE 3"))
    cand = "- **new winner**: better idiom"
    res = curate_and_write("p", cand, tmp_path)
    assert res.action == "replaced"
    assert res.replaced_index == 3
    entries = parse_entries(read_playbook("p", tmp_path))
    assert entries[2] == cand
    assert len(entries) == PLAYBOOK_CAP


def test_curate_at_cap_keep_discards_candidate(
    tmp_path: Path, at_cap: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing 10 are all judged stronger — candidate dropped."""
    before = read_playbook("p", tmp_path)
    monkeypatch.setattr(llm, "get_provider",
                        lambda: _stub_provider("KEEP"))
    res = curate_and_write("p", "- **new**: weaker idiom", tmp_path)
    assert res.action == "kept_existing"
    assert read_playbook("p", tmp_path) == before


def test_curate_at_cap_malformed_reply_falls_back_to_keep(
    tmp_path: Path, at_cap: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM emits prose instead of REPLACE/KEEP — conservative: KEEP."""
    before = read_playbook("p", tmp_path)
    monkeypatch.setattr(llm, "get_provider",
                        lambda: _stub_provider(
                            "I think replace 3 is fine actually"))
    res = curate_and_write("p", "- **new**: idiom", tmp_path)
    assert res.action == "kept_existing"
    assert read_playbook("p", tmp_path) == before


def test_curate_at_cap_provider_unavailable_keeps(
    tmp_path: Path, at_cap: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """complete_text returns None (provider unreachable)."""
    monkeypatch.setattr(llm, "get_provider",
                        lambda: _stub_provider(None))
    res = curate_and_write("p", "- **new**: idiom", tmp_path)
    assert res.action == "kept_existing"


def test_curate_at_cap_replace_out_of_range_keeps(
    tmp_path: Path, at_cap: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REPLACE 99 (n > CAP) → guard kicks in, fallback KEEP."""
    before = read_playbook("p", tmp_path)
    monkeypatch.setattr(llm, "get_provider",
                        lambda: _stub_provider("REPLACE 99"))
    res = curate_and_write("p", "- **new**: idiom", tmp_path)
    assert res.action == "kept_existing"
    assert read_playbook("p", tmp_path) == before


# ---------------------------------------------------------------------
# extract_idiom — pulls strategy info, calls LLM
# ---------------------------------------------------------------------

def _seed_strategy(conn: sqlite3.Connection, *, problem: str = "p",
                   scratch_path: str = "Problems/p/proofs/_strategy_s1.lean",
                   proposal_md: str = "decompose into A B C") -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
        (problem, "Problems/p/Manifest.md", db.now()),
    )
    gid = db.insert_goal(
        conn, problem=problem, slug="main",
        lean_path="Problems/p/Root.lean",
        statement="∀ p : ℕ, p.Prime → True",
        origin="root", difficulty=4,
    )
    return db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        scratch_path=scratch_path, proposal_md=proposal_md,
        created_by="pid-x",
    )


def test_extract_idiom_happy_path(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = _seed_strategy(conn)
    # Provide a proof file
    proof_path = tmp_path / "Problems" / "p" / "proofs" / "_strategy_s1.lean"
    proof_path.parent.mkdir(parents=True)
    proof_path.write_text("theorem s1 : True := trivial\n", encoding="utf-8")

    monkeypatch.setattr(
        llm, "get_provider",
        lambda: _stub_provider("- **trivial truth**: just `trivial`"))

    out = extract_idiom(sid, conn, tmp_path)
    assert out == "- **trivial truth**: just `trivial`"


def test_extract_idiom_missing_strategy_returns_none(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    assert extract_idiom(99999, conn, tmp_path) is None


def test_extract_idiom_skip_signal_returns_none(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = _seed_strategy(conn)
    monkeypatch.setattr(llm, "get_provider", lambda: _stub_provider("SKIP"))
    assert extract_idiom(sid, conn, tmp_path) is None


def test_extract_idiom_provider_unavailable_returns_none(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = _seed_strategy(conn)
    monkeypatch.setattr(llm, "get_provider", lambda: _stub_provider(None))
    assert extract_idiom(sid, conn, tmp_path) is None


# ---------------------------------------------------------------------
# maybe_record_idiom — orchestration + exception swallowing
# ---------------------------------------------------------------------

def test_maybe_record_idiom_writes_when_extract_succeeds(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = _seed_strategy(conn)
    monkeypatch.setattr(
        llm, "get_provider",
        lambda: _stub_provider("- **idiom**: a concise win"))
    res = maybe_record_idiom(sid, conn, tmp_path)
    assert res is not None
    assert res.action == "appended"
    assert "concise win" in read_playbook("p", tmp_path)


def test_maybe_record_idiom_skips_on_extract_none(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = _seed_strategy(conn)
    monkeypatch.setattr(llm, "get_provider", lambda: _stub_provider("SKIP"))
    res = maybe_record_idiom(sid, conn, tmp_path)
    assert res is None
    # No playbook.md created
    assert not (tmp_path / "Problems" / "p" / "playbook.md").exists()


def test_maybe_record_idiom_swallows_exceptions(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A buggy provider raising must NOT crash the dispatcher."""
    sid = _seed_strategy(conn)
    bad_provider = MagicMock()
    bad_provider.complete_text = MagicMock(
        side_effect=RuntimeError("provider blew up"))
    monkeypatch.setattr(llm, "get_provider", lambda: bad_provider)
    # Should not raise
    res = maybe_record_idiom(sid, conn, tmp_path)
    assert res is None


# ---------------------------------------------------------------------
# Atomic write — playbook is never half-written
# ---------------------------------------------------------------------

def test_curate_uses_atomic_replace(tmp_path: Path) -> None:
    """Verify .tmp file is removed after replace; observed file always
    contains a complete entry list."""
    cand = "- **a**: x"
    curate_and_write("p", cand, tmp_path)
    pdir = tmp_path / "Problems" / "p"
    assert (pdir / "playbook.md").exists()
    # No leftover temp
    assert not (pdir / "playbook.md.tmp").exists()
