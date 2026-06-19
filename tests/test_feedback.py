"""Agent framework-feedback questionnaire (`_feedback.py`)."""
from __future__ import annotations

import pytest

from Tooling.pipeline import _feedback

_OUT = "docs/internal/agent_feedback.md"


@pytest.fixture
def ws_on(tmp_path, monkeypatch):
    """Workspace with feedback enabled via env."""
    monkeypatch.setenv("ASTERISM_FEEDBACK_ENABLED", "true")
    return tmp_path


def _attempts(ws):
    d = ws / ".attempts"
    d.mkdir(exist_ok=True)
    return d


def test_disabled_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTERISM_FEEDBACK_ENABLED", "false")
    att = _attempts(tmp_path)
    _feedback.scratch_path(att).write_text("real friction", encoding="utf-8")
    _feedback.record_survivor(tmp_path, attempts_dir=att, kind="backward",
                              slug="g1", problem="p", outcome="exhausted")
    _feedback.record_death(tmp_path, kind="forward", slug="g2", problem="p",
                           reason="quota_exhausted")
    assert not (tmp_path / _OUT).exists()


def test_survivor_appends_with_metadata_prefix(ws_on):
    att = _attempts(ws_on)
    _feedback.scratch_path(att).write_text(
        "the gateway timeout message misled me\n"
        "evidence: rc=124 read like a build error",
        encoding="utf-8")
    _feedback.record_survivor(ws_on, attempts_dir=att, kind="backward",
                              slug="g1", problem="Geometry.x",
                              outcome="exhausted")
    content = (ws_on / _OUT).read_text(encoding="utf-8")
    assert content.startswith("# Agent framework feedback")     # header
    assert "the gateway timeout message misled me" in content
    assert "evidence: rc=124 read like a build error" in content
    # framework-owned metadata prefix
    assert "| backward |" in content
    assert "| exhausted |" in content
    assert "Geometry.x/g1]" in content


def test_survivor_none_and_missing_are_noop(ws_on):
    att = _attempts(ws_on)
    # explicit (none)
    _feedback.scratch_path(att).write_text("(none)", encoding="utf-8")
    _feedback.record_survivor(ws_on, attempts_dir=att, kind="backward",
                              slug="g1", problem="p", outcome="success")
    assert not (ws_on / _OUT).exists()
    # missing scratch
    _feedback.scratch_path(att).unlink()
    _feedback.record_survivor(ws_on, attempts_dir=att, kind="backward",
                              slug="g1", problem="p", outcome="success")
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
    att = _attempts(ws_on)
    _feedback.scratch_path(att).write_text("first thing", encoding="utf-8")
    _feedback.record_survivor(ws_on, attempts_dir=att, kind="backward",
                              slug="a", problem="p", outcome="success")
    _feedback.record_death(ws_on, kind="builder", slug="b", problem="p",
                           reason="spawn_fast_fail")
    content = (ws_on / _OUT).read_text(encoding="utf-8")
    assert content.count("# Agent framework feedback") == 1   # header once
    assert content.count("\n- [") == 2                        # two records
    assert "first thing" in content and "DIED: spawn_fast_fail" in content


def test_survivor_prompt_section_has_path_placeholder():
    # The standalone feedback prompt must carry the scratch-path placeholder so
    # attempt_feedback can substitute the per-spawn sandbox file.
    assert "{feedback_path}" in _feedback.SURVIVOR_PROMPT_SECTION
    # framing: asks for friction / suggestion / critique, not satisfaction
    low = _feedback.SURVIVOR_PROMPT_SECTION.lower()
    assert "friction" in low and "suggestion" in low and "critique" in low


# ---------------------------------------------------------------------
# attempt_feedback — the dedicated per-pipeline tail step
# ---------------------------------------------------------------------

def test_attempt_feedback_disabled_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTERISM_FEEDBACK_ENABLED", "false")
    from Tooling import agent
    calls = []
    monkeypatch.setattr(agent, "spawn_llm", lambda **k: calls.append(k) or 0)
    att = _attempts(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    _feedback.attempt_feedback(kind="strategist", sid="s1", slug="inject_done",
                               outcome="success", problem_dir=pdir,
                               attempts_dir=att, workspace=tmp_path)
    assert calls == []                               # no resume spawn when off
    assert not (tmp_path / _OUT).exists()


def test_attempt_feedback_resumes_session_and_records(ws_on, monkeypatch):
    from Tooling import agent
    seen: dict = {}

    def fake_spawn(**k):
        seen.update(k)
        # simulate the resumed agent writing its one-sentence answer
        _feedback.scratch_path(k["attempts_dir"]).write_text(
            "the audit retry prompt did not name the deprecated lemma",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    att = _attempts(ws_on)
    pdir = ws_on / "Problems" / "p"
    pdir.mkdir(parents=True)
    _feedback.attempt_feedback(kind="cleanup:audit", sid="sid-9", slug="Foo.lean",
                               outcome="success", problem_dir=pdir,
                               attempts_dir=att, workspace=ws_on)
    # resumed the just-finished session (not a cold spawn)
    assert seen["is_postmortem"] is True and seen["session_id"] == "sid-9"
    fb = (ws_on / _OUT).read_text(encoding="utf-8")
    assert "cleanup:audit" in fb and "p/Foo.lean" in fb
    assert "deprecated lemma" in fb


def test_attempt_feedback_no_sid_is_noop(ws_on, monkeypatch):
    from Tooling import agent
    calls = []
    monkeypatch.setattr(agent, "spawn_llm", lambda **k: calls.append(k) or 0)
    att = _attempts(ws_on)
    pdir = ws_on / "Problems" / "p"
    pdir.mkdir(parents=True)
    _feedback.attempt_feedback(kind="forward", sid="", slug="f",
                               outcome="success", problem_dir=pdir,
                               attempts_dir=att, workspace=ws_on)
    assert calls == []                               # empty sid → can't resume


def test_attempt_feedback_logs_diagnostic_on_dry_spawn(ws_on, monkeypatch, capsys):
    """When the resume spawn errors (rc!=0) and writes no scratch, surface a
    diagnostic instead of silently dropping the record — this dry-channel is
    what revealed the #33 1024-floor bug (every short-timeout feedback spawn
    died rc=1, recording nothing)."""
    from Tooling import agent
    monkeypatch.setattr(agent, "spawn_llm", lambda **k: 1)   # rc=1, no scratch
    att = _attempts(ws_on)
    pdir = ws_on / "Problems" / "p"
    pdir.mkdir(parents=True)
    _feedback.attempt_feedback(kind="cleanup:audit", sid="sid-x", slug="Foo.lean",
                               outcome="success", problem_dir=pdir,
                               attempts_dir=att, workspace=ws_on)
    out = capsys.readouterr().out
    assert "[feedback] cleanup:audit/Foo.lean: spawn rc=1" in out
    assert "scratch_written=False" in out
    assert not (ws_on / _OUT).exists()               # nothing landed (no scratch)
