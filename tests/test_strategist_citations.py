"""A line number of `Context.md` is only a line number of ONE Context.md.

Pure text + `tmp_path`. No DB, no daemon.
"""
from __future__ import annotations

from pathlib import Path

from Tooling.pipeline.strategist import citations


CONTEXT = """# Strategist context — Erdos.p1094

## Trigger

`trigger_kind`: routine

## Programme

rev 3 body line one
rev 3 body line two

## Recent decisions (newest first)

- tick=4 trigger=routine -> `Inject`
- tick=5 trigger=routine -> `Theorize`

## Active goals

**2 alive** — 2 open
"""


def _ctx(tmp_path: Path) -> Path:
    p = tmp_path / "Context.md"
    p.write_text(CONTEXT, encoding="utf-8")
    return p


def test_a_line_reference_becomes_the_section_it_fell_in(
        tmp_path: Path) -> None:
    """The failure, verbatim: decision 6039 on Erdos.p1094 said
    "(Context.md line 114)"; the Theorist's own Context.md ended at line
    107, so the pointer named nothing. Both documents come out of one
    renderer, so their SECTION names are the thing that survives the
    trip."""
    out = citations.resolve_context_line_refs(
        "the obstruction is recorded (Context.md line 8)", _ctx(tmp_path))
    assert out == ("the obstruction is recorded (Context.md § "
                   "`## Programme`)")


def test_a_range_names_every_section_it_crosses(tmp_path: Path) -> None:
    out = citations.resolve_context_line_refs(
        "see Context.md lines 8-15", _ctx(tmp_path))
    assert "`## Programme`" in out and "`## Recent decisions" in out
    assert "lines 8" not in out


def test_the_colon_and_dash_spellings_are_the_same_reference(
        tmp_path: Path) -> None:
    """Agents write `Context.md:21`, `line 21`, `lines 21–22` and
    `lines 21—22`; all four are one pointer into one file."""
    path = _ctx(tmp_path)
    for spelling in ("Context.md:8", "Context.md line 8",
                     "Context.md lines 8–9", "Context.md lines 8—9"):
        assert "`## Programme`" in citations.resolve_context_line_refs(
            spelling, path), spelling


def test_an_unresolvable_reference_says_whose_number_it_is(
        tmp_path: Path) -> None:
    """Not kept (it would go on pointing at nothing) and not dropped
    (the writer meant something by it): rewritten to the one fact the
    downstream reader could not have known."""
    out = citations.resolve_context_line_refs(
        "as Context.md line 900 shows", _ctx(tmp_path))
    assert "line 900 of the strategist's own wake" in out
    assert "not of this file" in out


def test_a_missing_document_is_not_a_lost_request(tmp_path: Path) -> None:
    """We know WHICH document was meant and cannot read it — enough to
    tell the reader the number is not its own."""
    out = citations.resolve_context_line_refs(
        "per Context.md line 113", tmp_path / "gone.md")
    assert "strategist's own wake" in out


def test_with_no_candidate_document_the_text_is_left_alone() -> None:
    """Nobody said which document the writer was looking at (the human
    channel has no wake directory), so there is no basis for a claim
    about whose lines these are."""
    text = "per Context.md line 113"
    assert citations.resolve_context_line_refs(text, None) is text


def test_other_documents_line_numbers_are_left_alone(
        tmp_path: Path) -> None:
    """A citation into a theory document points at a file on the
    Project's shelf that does not change under the reader. Rewriting it
    would take away a precise pointer for nothing."""
    text = ("the CRT bound ignores the unit tests (g741, lines 346–354) "
            "and Context.md line 8 records the obstruction")
    out = citations.resolve_context_line_refs(text, _ctx(tmp_path))
    assert "(g741, lines 346–354)" in out
    assert "`## Programme`" in out


def test_text_with_no_reference_is_returned_unchanged(
        tmp_path: Path) -> None:
    text = "Prove or refute `uniform_divisor_sieve_emptiness`."
    assert citations.resolve_context_line_refs(text, _ctx(tmp_path)) is text


def test_both_request_fields_are_resolved(tmp_path: Path) -> None:
    """The objective carries the pointer as often as the situation: it
    is where the Strategist names the statement it wants and says where
    that statement stands."""
    got = citations.resolve_theory_request(
        {"objective": "prove S (Context.md line 8)",
         "situation": "the record stands at Context.md line 14",
         "step_index": 2},
        _ctx(tmp_path))
    assert "`## Programme`" in got["objective"]
    assert "`## Recent decisions" in got["situation"]
    assert got["step_index"] == 2


def test_the_callers_payload_is_not_mutated(tmp_path: Path) -> None:
    payload = {"objective": "prove S (Context.md line 8)"}
    citations.resolve_theory_request(payload, _ctx(tmp_path))
    assert payload["objective"] == "prove S (Context.md line 8)"


def test_a_document_with_no_headings_names_no_section(
        tmp_path: Path) -> None:
    """Nothing to name is not a licence to invent one: the reference
    takes the unresolved form, which at least says whose number it is."""
    flat = tmp_path / "Context.md"
    flat.write_text("one\ntwo\nthree\n", encoding="utf-8")
    out = citations.resolve_context_line_refs("Context.md line 2", flat)
    assert "line 2 of the strategist's own wake" in out


def test_the_documents_title_is_a_section_like_any_other(
        tmp_path: Path) -> None:
    """Context.md opens with `# Strategist context — <problem>`, and a
    reference into that opening resolves to it. That heading is as
    stable across the two documents as any `##` below it."""
    out = citations.resolve_context_line_refs(
        "Context.md line 1", _ctx(tmp_path))
    assert "`# Strategist context" in out


# ── the commit path stores the request as the theorist will read it ──

def test_the_commit_resolves_the_request_against_this_wakes_context(
        tmp_path: Path) -> None:
    """The whole trip, end to end: the seat writes a line number of the
    document in front of it, and what lands in the row — which is what
    the Theorist's `## Trigger` renders — names a section instead."""
    import json
    import sqlite3  # noqa: F401 — the connection comes from state.db
    from Tooling.pipeline.strategist import commit as _commit
    from Tooling.pipeline.strategist import parse_decision
    from Tooling.state import db as _db
    from Tooling.state import groups as _groups

    ws = tmp_path / "ws"
    (ws / "Problems" / "P" / "p1").mkdir(parents=True)
    conn = _db.connect(ws / "asterism.db")
    _db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
                 " VALUES ('P.p1', ?, 1)", (_db.now(),))
    conn.commit()
    gid = _groups.ensure_top_group(conn, "P.p1")

    attempts = tmp_path / "_attempts"
    attempts.mkdir()
    (attempts / "Context.md").write_text(CONTEXT, encoding="utf-8")

    d, err = parse_decision(json.dumps({
        "kind": "Theorize",
        "objective": "prove S; where it stands: Context.md line 8",
        "situation": "the last wake decided this at Context.md line 14"}))
    assert err == "", err
    out = _commit.commit_decisions(
        [d], conn, problem="P.p1", tick=0, trigger_kind="routine",
        workspace=ws, group_id=gid, attempts_dir=attempts)[0]

    payload = json.loads(conn.execute(
        "SELECT payload FROM strategist_decisions WHERE id = ?",
        (out.decision_row_id,)).fetchone()["payload"])
    assert "`## Programme`" in payload["objective"]
    assert "`## Recent decisions" in payload["situation"]
    assert "line 8" not in payload["objective"]


def test_without_this_wakes_directory_the_request_is_stored_as_written(
        tmp_path: Path) -> None:
    """A human command files a Theorize through the same appliers and
    has no wake directory. Nothing is invented for it: the text is the
    person's."""
    import json
    from Tooling.pipeline.strategist import commit as _commit
    from Tooling.pipeline.strategist import parse_decision
    from Tooling.state import db as _db
    from Tooling.state import groups as _groups

    ws = tmp_path / "ws2"
    (ws / "Problems" / "P" / "p1").mkdir(parents=True)
    conn = _db.connect(ws / "asterism.db")
    _db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
                 " VALUES ('P.p1', ?, 1)", (_db.now(),))
    conn.commit()
    gid = _groups.ensure_top_group(conn, "P.p1")
    d, err = parse_decision(json.dumps({
        "kind": "Theorize", "objective": "prove S",
        "situation": "as Context.md line 113 says"}))
    assert err == "", err
    out = _commit.commit_decisions(
        [d], conn, problem="P.p1", tick=0, trigger_kind="routine",
        workspace=ws, group_id=gid, actor=_commit.ACTOR_HUMAN)[0]
    payload = json.loads(conn.execute(
        "SELECT payload FROM strategist_decisions WHERE id = ?",
        (out.decision_row_id,)).fetchone()["payload"])
    assert payload["situation"] == "as Context.md line 113 says"
