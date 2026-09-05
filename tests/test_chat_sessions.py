"""The Assistant's transcripts on disk (`serve/chat_sessions.py`).

HID §1.1 asked for per-Project sessions and got one live conversation
per Project held in a dict on the serve process. The redesign
(web/docs/assistant_redesign_2026-09-06.md §2) makes them MANY, named,
and durable: JSON files under `<workspace>/.asterism/chat/<project>/`,
runtime state beside the rest of `.asterism/` and never the daemon's
DB — this is not proof state.

What is pinned here is the store's own law, with no HTTP in the way:
the shape of a record, the title derivation, the reuse of an empty
session, what truncation is allowed to do, and the fence around an id
that is about to become a path.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from Tooling.serve import chat_sessions as cs


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "Problems").mkdir()
    return tmp_path


def _new(workspace: Path, project: str = "_global") -> dict:
    return cs.create(workspace, project, model="claude-sonnet-5",
                     provider="claude")


# -- the record ------------------------------------------------------------


def test_a_new_session_is_a_file_the_summary_describes(
    workspace: Path,
) -> None:
    rec = _new(workspace, "Erdos")
    path = (workspace / ".asterism" / "chat" / "Erdos"
            / f"{rec['id']}.json")
    assert path.is_file(), "the store is files under .asterism/, not the DB"
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == rec
    assert rec["project"] == "Erdos"
    assert rec["turns"] == []
    assert rec["handle"] is None and rec["page_key"] is None
    assert rec["title_custom"] is False
    assert cs.get(workspace, rec["id"]) == rec
    assert set(cs.summary(rec)) == {"id", "title", "updated_at",
                                    "created_at", "turns", "model",
                                    "provider"}
    assert cs.summary(rec)["turns"] == 0, "the summary counts, not carries"


def test_a_session_belongs_to_one_project(workspace: Path) -> None:
    """§1.1-2: every Project gets its own transcripts. A listing that
    crossed shelves would put an Erdos question on a Topology page."""
    mine = _new(workspace, "Erdos")
    _new(workspace, "Topology")
    assert [s["id"] for s in cs.list_for(workspace, "Erdos")] == [mine["id"]]
    # …and the id still resolves globally: the panel holds an id, not a
    # (project, id) pair, and the record names its own shelf.
    assert cs.get(workspace, mine["id"])["project"] == "Erdos"


def test_the_unknown_is_absent_not_an_error(workspace: Path) -> None:
    assert cs.get(workspace, "0" * 32) is None
    assert cs.list_for(workspace, "Erdos") == []
    assert cs.delete(workspace, "0" * 32) is False


# -- titles ----------------------------------------------------------------


def test_the_title_is_the_first_line_of_the_first_question(
    workspace: Path,
) -> None:
    rec = _new(workspace)
    assert rec["title"] == ""
    rec = cs.append_user(workspace, rec["id"],
                         "  why   is p1\nstalled?  \nand the rest")
    assert rec["title"] == "why is p1"
    # a second question does not rename the conversation
    rec = cs.append_user(workspace, rec["id"], "and why is that?")
    assert rec["title"] == "why is p1"


def test_a_long_first_line_is_clipped_to_sixty(workspace: Path) -> None:
    long = "why " * 40
    assert len(cs.derive_title(long)) <= 60
    assert cs.derive_title(long).startswith("why why")
    assert cs.derive_title("") == ""


def test_rename_sticks_and_an_empty_rename_restores_the_derivation(
    workspace: Path,
) -> None:
    """The design's `title_custom`: once renamed the title is the
    person's, and the only way back to the machine's is to clear it."""
    rec = _new(workspace)
    cs.append_user(workspace, rec["id"], "why is p1 stalled?")
    rec = cs.rename(workspace, rec["id"], "  the p1 question  ")
    assert rec["title"] == "the p1 question" and rec["title_custom"] is True
    # a later question must not overwrite the person's name for it
    rec = cs.append_user(workspace, rec["id"], "something else entirely")
    assert rec["title"] == "the p1 question"
    rec = cs.rename(workspace, rec["id"], "   ")
    assert rec["title_custom"] is False
    assert rec["title"] == "why is p1 stalled?"


def test_renaming_an_unknown_session_is_a_KeyError(workspace: Path) -> None:
    with pytest.raises(KeyError):
        cs.rename(workspace, "0" * 32, "x")


# -- one empty session, not a drawer full of them --------------------------


def test_creating_twice_reuses_the_empty_session(workspace: Path) -> None:
    """§2: a zero-turn session is legal and is REUSED. Otherwise every
    click of `+ new conversation` mints another blank row and the fold
    fills with nothing."""
    first = _new(workspace, "Erdos")
    again = _new(workspace, "Erdos")
    assert again["id"] == first["id"]
    assert len(cs.list_for(workspace, "Erdos")) == 1
    cs.append_user(workspace, first["id"], "why is p1 stalled?")
    third = _new(workspace, "Erdos")
    assert third["id"] != first["id"]
    assert len(cs.list_for(workspace, "Erdos")) == 2
    # a sibling Project's empty session is not this one's
    other = _new(workspace, "Topology")
    assert other["id"] != third["id"]


# -- ordering --------------------------------------------------------------


def test_the_listing_is_newest_activity_first(workspace: Path) -> None:
    a = _new(workspace, "Erdos")
    cs.append_user(workspace, a["id"], "first")
    time.sleep(0.005)
    b = _new(workspace, "Erdos")
    cs.append_user(workspace, b["id"], "second")
    assert [s["id"] for s in cs.list_for(workspace, "Erdos")] == [b["id"],
                                                                 a["id"]]
    time.sleep(0.005)
    cs.append_user(workspace, a["id"], "third")
    assert [s["id"] for s in cs.list_for(workspace, "Erdos")] == [a["id"],
                                                                 b["id"]]


# -- turns -----------------------------------------------------------------


def test_the_assistant_turn_carries_its_tool_rows(workspace: Path) -> None:
    rec = _new(workspace)
    cs.append_user(workspace, rec["id"], "why?")
    rows = [{"id": "toolu_1", "name": "Glob", "input": {"pattern": "*.ts"},
             "ok": True, "ms": 1210, "result": "21 files"}]
    rec = cs.append_assistant(workspace, rec["id"], "because…", ok=True,
                              tools=rows)
    turn = rec["turns"][-1]
    assert turn["role"] == "assistant" and turn["text"] == "because…"
    assert turn["ok"] is True and turn["note"] is None
    assert turn["tools"] == rows
    assert cs.summary(rec)["turns"] == 2


def test_a_question_whose_answer_never_started_is_not_kept(
    workspace: Path,
) -> None:
    """§2: a user turn whose spawn failed is not persisted — the panel
    rolls the text back into the composer, and a transcript that showed
    the question with no answer would contradict it."""
    rec = _new(workspace)
    cs.append_user(workspace, rec["id"], "first")
    cs.append_assistant(workspace, rec["id"], "answer", ok=True)
    rec = cs.append_user(workspace, rec["id"], "doomed")
    rec = cs.pop_last_user(workspace, rec["id"])
    assert [t["text"] for t in rec["turns"]] == ["first", "answer"]
    # …and it will not eat a settled answer if called twice
    rec = cs.pop_last_user(workspace, rec["id"])
    assert [t["text"] for t in rec["turns"]] == ["first", "answer"]


# -- truncation (edit & re-ask) --------------------------------------------


def _conversation(workspace: Path) -> dict:
    rec = _new(workspace)
    cs.append_user(workspace, rec["id"], "why is p1 stalled?")
    cs.append_assistant(workspace, rec["id"], "it waits on the strategist",
                        ok=True)
    cs.append_user(workspace, rec["id"], "and why is that?")
    return cs.append_assistant(workspace, rec["id"], "because…", ok=True)


def test_truncate_drops_the_later_turns(workspace: Path) -> None:
    rec = _conversation(workspace)
    rec = cs.truncate(workspace, rec["id"], 2)
    assert [t["text"] for t in rec["turns"]] == [
        "why is p1 stalled?", "it waits on the strategist"]


def test_truncate_must_land_on_a_user_turn(workspace: Path) -> None:
    """`edit & re-ask` edits a QUESTION. Truncating at an answer would
    leave a transcript whose next turn re-answers nothing."""
    rec = _conversation(workspace)
    for bad in (1, 3, 4, -1):
        with pytest.raises(ValueError):
            cs.truncate(workspace, rec["id"], bad)
    assert len(cs.get(workspace, rec["id"])["turns"]) == 4


def test_truncate_clears_the_engines_handle(workspace: Path) -> None:
    """§2 continuity: no CLI can rewind a session, so a truncated
    transcript must be planned COLD — the replay block carries the
    kept turns instead. A handle left behind would resume the engine's
    memory of the turns the person just deleted."""
    rec = _conversation(workspace)
    rec = cs.set_handle(workspace, rec["id"], "uuid-1", "problem:Erdos.p1")
    assert rec["handle"] == "uuid-1" and rec["page_key"] == "problem:Erdos.p1"
    rec = cs.truncate(workspace, rec["id"], 0)
    assert rec["handle"] is None and rec["page_key"] is None
    assert rec["turns"] == []
    # turn 0 is gone, so the derived title goes with it
    assert rec["title"] == ""


# -- the id is about to become a path --------------------------------------


def test_an_id_that_is_not_an_id_never_touches_the_filesystem(
    workspace: Path,
) -> None:
    """Every entry point takes an id straight off the wire and joins it
    to a directory. The regex is the fence: uuid4 hex, nothing else."""
    rec = _new(workspace)
    outside = workspace / ".asterism" / "chat" / "secret.json"
    outside.write_text("{}", encoding="utf-8")
    for bad in ("", "..", "../secret", "_global/" + rec["id"], "*",
                rec["id"].upper(), rec["id"] + ".json", "a" * 31):
        assert cs.get(workspace, bad) is None, bad
        assert cs.delete(workspace, bad) is False, bad
        assert cs.pop_last_user(workspace, bad) is None, bad
        with pytest.raises(KeyError):
            cs.rename(workspace, bad, "x")
        with pytest.raises(KeyError):
            cs.truncate(workspace, bad, 0)
    assert outside.exists(), "a traversal id reached outside the store"
    assert cs.get(workspace, rec["id"]) is not None


def test_a_project_key_that_is_not_a_key_is_refused(workspace: Path) -> None:
    """The second half of the same fence: the key is a directory name."""
    for bad in ("../etc", "a/b", "", "."):
        with pytest.raises(ValueError):
            cs.create(workspace, bad, model="m", provider="claude")
        assert cs.list_for(workspace, bad) == []
