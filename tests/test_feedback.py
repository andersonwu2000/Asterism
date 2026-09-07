"""Agent framework-feedback sink (`_feedback.py`) + the `feedback` tool.

Owner ruling 2026-09-07: the end-of-run survivor leg — one extra
`--resume` spawn per finished pipeline, asking the agent to write a
sentence into a scratch file — is retired. Agents file mid-run through
the `feedback(note, evidence)` MCP tool instead. What is pinned here is
the writer's record shape (unchanged, so the lab still counts it), the
tool's behaviour, and the fact that no pipeline spawns that extra leg
any more.
"""
from __future__ import annotations

import pytest

from Tooling.pipeline import _feedback

# Owner ruling 2026-09-06: the private docs tree moved out of this repo, so
# production must never write into `docs/internal/`. The sink is runtime
# state — it belongs in `.asterism/` with the rest of it (already gitignored,
# and already a `PRIVATE_READ_SUBTREES` deny-root, so no spawn can read it).
_OUT = ".asterism/agent_feedback.md"


@pytest.fixture
def ws_on(tmp_path, monkeypatch):
    """Workspace with feedback enabled via env."""
    monkeypatch.setenv("ASTERISM_FEEDBACK_ENABLED", "true")
    return tmp_path


def test_disabled_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTERISM_FEEDBACK_ENABLED", "false")
    assert _feedback.record_note(tmp_path, kind="backward", slug="g1",
                                 problem="p", note="real friction") is False
    _feedback.record_death(tmp_path, kind="forward", slug="g2", problem="p",
                           reason="quota_exhausted")
    assert not (tmp_path / _OUT).exists()


def test_note_appends_with_metadata_prefix(ws_on):
    assert _feedback.record_note(
        ws_on, kind="backward", slug="g1", problem="Geometry.x",
        note="the gateway timeout message misled me",
        evidence="rc=124 read like a build error") is True
    content = (ws_on / _OUT).read_text(encoding="utf-8")
    assert content.startswith("# Agent framework feedback")     # header
    assert "the gateway timeout message misled me" in content
    assert "evidence: rc=124 read like a build error" in content
    # framework-owned metadata prefix
    assert "| backward |" in content
    assert f"| {_feedback.IN_FLIGHT} |" in content
    assert "Geometry.x/g1]" in content


def test_a_note_is_always_one_record(ws_on):
    """The agent hands over free text; the file is line-structured and
    `count_records` counts `RECORD_MARK` lines. A note carrying newlines
    would otherwise split into a record plus a line that is not one."""
    _feedback.record_note(
        ws_on, kind="strategist", slug="routine", problem="p",
        note="first\nsecond\n\n  third",
        evidence="line one\nline two")
    text = (ws_on / _OUT).read_text(encoding="utf-8")
    assert _feedback.count_records(text) == 1
    assert "first second third" in text
    assert "evidence: line one line two" in text


def test_a_note_is_capped_so_one_spawn_cannot_evict_the_others(ws_on):
    """The ring keeps whole RECORDS, so an agent pasting a transcript
    would push every other spawn's sentence out by volume."""
    _feedback.record_note(ws_on, kind="librarian", slug="s", problem="p",
                          note="x" * 5000, evidence="y" * 5000)
    line = [ln for ln in (ws_on / _OUT).read_text(encoding="utf-8")
            .splitlines() if ln.startswith(_feedback.RECORD_MARK)][0]
    assert len(line) < _feedback.MAX_NOTE_CHARS + 200
    assert line.endswith("…")


def test_an_empty_note_is_not_a_record(ws_on):
    assert _feedback.record_note(ws_on, kind="adversary", slug="r1",
                                 problem="p", note="   ") is False
    assert not (ws_on / _OUT).exists()


def test_death_writes_cause_line(ws_on):
    _feedback.record_death(ws_on, kind="forward", slug="g2",
                           problem="Geometry.x", reason="quota_exhausted")
    content = (ws_on / _OUT).read_text(encoding="utf-8")
    assert "(dead)" in content                  # death marker
    assert "DIED: quota_exhausted" in content
    assert "| forward |" in content
    assert "Geometry.x/g2]" in content


def test_records_accumulate_one_header(ws_on):
    _feedback.record_note(ws_on, kind="backward", slug="a", problem="p",
                          note="first thing")
    _feedback.record_death(ws_on, kind="builder", slug="b", problem="p",
                           reason="spawn_fast_fail")
    content = (ws_on / _OUT).read_text(encoding="utf-8")
    assert content.count("# Agent framework feedback") == 1   # header once
    assert content.count("\n- [") == 2                        # two records
    assert "first thing" in content and "DIED: spawn_fast_fail" in content


def test_feedback_file_is_a_ring_of_whole_records(ws_on, monkeypatch):
    """Owner call 2026-08-29: feedback is short-shelf-life signal — an
    unattended cloud run must not grow the file without bound. The write
    chokepoint keeps only the newest MAX_ENTRIES records, in WHOLE-record
    units (a continuation line lives and dies with its record), and the
    header block survives every trim."""
    assert _feedback.MAX_ENTRIES == 1000        # the owner's number
    monkeypatch.setattr(_feedback, "MAX_ENTRIES", 5)
    for i in range(3):
        _feedback.record_death(ws_on, kind="forward", slug=f"g{i}",
                               problem="p", reason=f"reason_{i}")
    _feedback.record_note(ws_on, kind="backward", slug="keeper", problem="p",
                          note="keeper friction",
                          evidence="with a continuation line")
    for i in range(3, 7):
        _feedback.record_death(ws_on, kind="forward", slug=f"g{i}",
                               problem="p", reason=f"reason_{i}")
    content = (ws_on / _OUT).read_text(encoding="utf-8")
    # 8 appended, 5 kept: the note + the last four deaths
    assert content.count("\n- [") == 5
    assert content.startswith("# Agent framework feedback")   # header intact
    assert "keeper friction" in content
    assert "evidence: with a continuation line" in content    # rode along
    for gone in ("reason_0", "reason_1", "reason_2"):
        assert gone not in content
    assert "reason_3" in content and "reason_6" in content


def test_the_model_column_resolves_from_the_seat_not_the_label(
    ws_on, monkeypatch,
):
    """There is no `forward.model` or `cleanup:audit.model` key, so
    resolving from the record LABEL wrote `?` into every such record
    (2026-08-13)."""
    from Tooling.core import config
    models = {"formalizer.model": "seat-model", "feedback.enabled": True}
    monkeypatch.setattr(
        config, "get",
        lambda key, **kw: models.get(key, kw.get("default")))
    _feedback.record_note(ws_on, kind="forward", slug="s", problem="p",
                          note="n", seat="formalizer")
    assert "| seat-model |" in (ws_on / _OUT).read_text(encoding="utf-8")


# ---------------------------------------------------------------------
# the retired survivor leg
# ---------------------------------------------------------------------

def test_the_survivor_leg_is_gone_from_the_module():
    """Retired 2026-09-07. Named here rather than left to rot: the leg
    cost a spawn per pipeline, reached only agents that survived to a
    resumable terminal, and asked at the one moment the friction is
    furthest away."""
    for gone in ("attempt_feedback", "record_survivor", "scratch_path",
                 "SURVIVOR_PROMPT_SECTION"):
        assert not hasattr(_feedback, gone), gone
    from Tooling.pipeline import PROMPT_DIR
    assert not (PROMPT_DIR / "_shared" / "feedback_survivor.md").exists()
    # The lab reads these three; they stay.
    assert _feedback.RECORD_MARK == "- ["
    assert callable(_feedback.feedback_path)
    assert callable(_feedback.count_records)


def test_no_pipeline_spawns_an_extra_leg_after_it_finishes(
    ws_on, monkeypatch,
):
    """The mechanism pin, read off the retry loop rather than the
    source: run the shared loop to a terminal with feedback ENABLED and
    count the spawns. Before the retirement this was 2 — the work spawn
    and the resumed questionnaire."""
    import sqlite3

    from Tooling.pipeline import PipelineResult, _retry

    spawns: list = []

    def spawn_fn(ctx) -> int:
        spawns.append(ctx.sid)
        return 0

    result = _retry.run_with_session_retries(
        conn=sqlite3.connect(":memory:"), goal_id=None,
        pipeline_id="pid", budget_threshold=3, shelve_threshold=0,
        attempts_dir=ws_on, spawn_fn=spawn_fn,
        parse_fn=lambda: PipelineResult(outcome="success"),
        postmortem_fn=lambda _sid: None, workspace=ws_on, kind="strategist")

    assert result.outcome == "success"
    assert len(spawns) == 1, "a finished pipeline spawned an extra leg"
    assert not (ws_on / _OUT).exists()
