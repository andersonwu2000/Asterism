"""`inspect` — three owner rulings of 2026-08-29.

1. A delivery-budget deferral names ONLY the answer that does not fit.
   Until now the first oversize answer took every later query with it
   ("everything later waits too"), so one 12KB section held ten
   one-line questions hostage in the same call.
2. `outline: true` on a roster-sized file must point: CATALOG.md has
   1,333 sections and its whole map is 30-60K chars — shipping it IS
   shipping the roster the 2026-08-15 ruling refused. Past
   `OUTLINE_INLINE_MAX` sections the caller names a prefix / regex and
   gets at most `OUTLINE_MATCH_MAX` hits; without one it gets the
   prefix-count table and the three ways in.
3. `{"decl": "gNNNN"}` — the label TREE.md / Context.md print for a
   goal — resolves by row id, not by substring over slugs.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from Tooling.knowledge import workspace_query as wq
from Tooling.state import db as _db


# ── 1. deferral is per answer, not "everything after" ────────────────

def _batch(tmp_path: Path, big_at: int, n: int = 11) -> "list[dict]":
    """`n` reads; the one at 1-based position `big_at` is oversize."""
    (tmp_path / "big.md").write_text("b" * 20_000 + "\n", encoding="utf-8")
    qs = []
    for i in range(1, n + 1):
        if i == big_at:
            qs.append({"read": "big.md", "lines": "1-"})
            continue
        (tmp_path / f"s{i}.md").write_text(f"needle-{i}\n", encoding="utf-8")
        qs.append({"read": f"s{i}.md"})
    return qs


def _delivered(out: str, n: int = 11) -> "set[int]":
    return {i for i in range(1, n + 1) if f"needle-{i}" in out}


def test_only_the_oversize_answer_is_deferred(tmp_path: Path) -> None:
    out = wq.run_queries(_batch(tmp_path, big_at=3), cwd=tmp_path,
                         delivery_chars=3_000)
    assert len(out) <= 3_000, "the reply still fits the transport"
    assert _delivered(out) == set(range(1, 12)) - {3}, out[-400:]
    assert "not answered" in out and '[3] {"lines": "1-", "read": "big.md"}' in out
    assert "bbbb" not in out, "the deferred answer is whole-or-absent"
    assert out.count("Send these in a second call") == 1


@pytest.mark.parametrize("big_at", [3, 6, 11])
def test_the_position_of_the_oversize_query_does_not_change_the_rest(
    tmp_path: Path, big_at: int,
) -> None:
    out = wq.run_queries(_batch(tmp_path, big_at=big_at), cwd=tmp_path,
                         delivery_chars=3_000)
    assert _delivered(out) == set(range(1, 12)) - {big_at}
    assert f"[{big_at}] " in out.split("second call:")[-1]


def test_deferred_queries_are_listed_in_send_order(tmp_path: Path) -> None:
    """A deferral can now sit between two delivered answers, and the
    hand-back of the last answer (room for the note) appends late — the
    note must still speak in the order the caller sent."""
    for i in range(8):
        (tmp_path / f"f{i}.md").write_text(("%d" % i) * 2_500 + "\n",
                                           encoding="utf-8")
    qs = [{"read": f"f{i}.md"} for i in range(8)]
    qs.insert(2, {"read": "f0.md", "lines": "1-"})  # index 3, oversize-ish
    out = wq.run_queries(qs, cwd=tmp_path, delivery_chars=5_200)
    assert len(out) <= 5_200
    tail = out.split("second call:")[-1]
    idx = [int(m) for m in re.findall(r"\[(\d+)\]", tail)]
    assert idx == sorted(idx), tail


def test_an_answer_alone_over_the_whole_budget_is_still_deferred_by_name(
    tmp_path: Path,
) -> None:
    """Unchanged: a non-first answer larger than the entire ceiling can
    only be deferred (the first query alone rides whatever it costs)."""
    out = wq.run_queries(_batch(tmp_path, big_at=2, n=3), cwd=tmp_path,
                         delivery_chars=1_000)
    assert _delivered(out, 3) == {1, 3}
    assert "[2]" in out.split("second call:")[-1]


# ── 2. outline must point on a roster-sized file ─────────────────────

def _roster(tmp_path: Path, n: int = 1_333, name: str = "CATALOG.md") -> Path:
    """Exactly `n` sections, catalog-shaped: the `#` title plus entries
    — 1,000 `uc_*`, 200 `aux_*`, the rest `lem_*`, the prefix skew a
    real catalog has."""
    body = [f"# Proved catalog — test ({n - 1} entries)", ""]
    for i in range(n - 1):
        pre = "uc" if i < 1_000 else "aux" if i < 1_200 else "lem"
        body += [f"## {pre}_{i:04d}_thing  (theorem)", "",
                 f"    theorem {pre}_{i:04d}_thing : True", ""]
    p = tmp_path / name
    p.write_text("\n".join(body), encoding="utf-8")
    return p


def test_a_roster_outline_without_a_filter_is_refused_with_the_prefix_table(
    tmp_path: Path,
) -> None:
    _roster(tmp_path)
    out = wq.run_queries([{"read": "CATALOG.md", "outline": True}],
                         cwd=tmp_path)
    assert "1333 sections" in out
    assert "uc_0500_thing" not in out, "the refusal must not ship the map"
    assert "outline_prefix" in out and '"decl"' in out and '"grep"' in out
    assert "uc (1000)" in out and "aux (200)" in out and "lem (132)" in out
    table = [ln for ln in out.splitlines() if "heading prefixes" in ln][0]
    assert len(table) < 1_500, f"{len(table)} chars of table"
    assert len(out) < 2_000, f"{len(out)} chars — a refusal, not a roster"


def test_a_prefix_within_the_hit_cap_returns_the_slice(tmp_path: Path) -> None:
    _roster(tmp_path)
    out = wq.run_queries([{"read": "CATALOG.md", "outline": True,
                           "outline_prefix": "AUX_119"}], cwd=tmp_path)
    assert "10 match" in out, "case-insensitive prefix, 10 hits"
    assert "aux_1190_thing" in out and "aux_1189_thing" not in out
    assert "lines " in out and "chars" in out, "still the map, not the text"
    assert 'sections: ["<heading text>"]' in out


def test_a_prefix_past_the_hit_cap_is_refused_and_asks_for_narrower(
    tmp_path: Path,
) -> None:
    _roster(tmp_path)
    out = wq.run_queries([{"read": "CATALOG.md", "outline": True,
                           "outline_prefix": "uc"}], cwd=tmp_path)
    assert "1000 of 1333 headings match" in out
    assert "narrow" in out and "uc_0500_thing" not in out


def test_outline_grep_is_a_regex_and_a_bad_one_says_so(tmp_path: Path) -> None:
    _roster(tmp_path)
    out = wq.run_queries([{"read": "CATALOG.md", "outline": True,
                           "outline_grep": r"^uc_099\d_"}], cwd=tmp_path)
    assert "10 match" in out and "uc_0995_thing" in out
    out2 = wq.run_queries([{"read": "CATALOG.md", "outline": True,
                            "outline_grep": "("}], cwd=tmp_path)
    assert "bad `outline_grep` pattern" in out2


def test_a_filter_with_no_hits_hands_back_the_prefix_table(
    tmp_path: Path,
) -> None:
    _roster(tmp_path)
    out = wq.run_queries([{"read": "CATALOG.md", "outline": True,
                           "outline_prefix": "zzz"}], cwd=tmp_path)
    assert "no heading matches prefix 'zzz'" in out
    assert "uc (1000)" in out, "the table is the way to a prefix that exists"


def test_a_file_at_the_inline_limit_still_outlines_whole(tmp_path: Path) -> None:
    _roster(tmp_path, n=wq.OUTLINE_INLINE_MAX, name="small.md")
    out = wq.run_queries([{"read": "small.md", "outline": True}], cwd=tmp_path)
    assert f"{wq.OUTLINE_INLINE_MAX} sections" in out
    assert "uc_0000_thing" in out and "uc_0118_thing" in out
    assert "outline_prefix" not in out, "no refusal on a file that fits"


def test_a_whole_read_of_a_roster_file_teaches_the_prefix_way_in(
    tmp_path: Path,
) -> None:
    """`_whole_read_refusal` inlines the outline when it is small; on a
    roster file the outline is itself the refusal — so the whole-read
    refusal must carry the prefix table, not "outline: true maps them"."""
    _roster(tmp_path)
    out = wq.run_queries([{"read": "CATALOG.md"}], cwd=tmp_path)
    assert "whole file is" in out
    assert "outline_prefix" in out and "uc (1000)" in out
    assert "uc_0500_thing" not in out


# ── 3. decl by goal id ───────────────────────────────────────────────

@pytest.fixture
def seeded(tmp_path: Path) -> "tuple[Path, int]":
    (tmp_path / "Tooling").mkdir()
    here = tmp_path / "Problems" / "Combinatorics" / "union_closed"
    (here / "proofs").mkdir(parents=True)
    (here / "proofs" / "L_uc_four.lean").write_text(
        "import Mathlib\ntheorem uc_four : True := by\n  trivial\n",
        encoding="utf-8")
    conn = _db.connect(tmp_path / "asterism.db")
    _db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
                 " VALUES (?, ?, 1)", ("union_closed", _db.now()))
    gid = _db.insert_goal(
        conn, problem="union_closed", slug="uc_four",
        lean_path="Problems/Combinatorics/union_closed/proofs/L_uc_four.lean",
        statement="True", origin="root")
    conn.commit()
    conn.close()
    return here, gid


def test_decl_accepts_a_goal_id_label(seeded) -> None:
    here, gid = seeded
    out = wq.run_queries([{"decl": f"g{gid}"}], cwd=here)
    assert "uc_four  [open]" in out, out
    assert "L_uc_four.lean" in out and "theorem uc_four" in out
    assert "no declaration named" not in out


def test_decl_by_slug_is_unchanged_and_an_unknown_id_is_a_clean_miss(
    seeded,
) -> None:
    here, gid = seeded
    by_slug = wq.run_queries([{"decl": "uc_four"}], cwd=here)
    by_id = wq.run_queries([{"decl": f"g{gid}"}], cwd=here)
    assert by_slug.split("\n", 1)[1] == by_id.split("\n", 1)[1], (
        "same record, same rendering — only the label line differs")
    miss = wq.run_queries([{"decl": f"g{gid + 1000}"}], cwd=here)
    assert "no declaration named" in miss
