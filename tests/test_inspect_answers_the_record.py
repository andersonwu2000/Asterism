"""Three in-flight agent reports on `inspect`, 2026-09-07 — each a
place where the tool said something its own record contradicts.

1. `inspect({"decl": ...})` promises "the latest strategy failure or
   decline detail for pending-review goals" and delivered status, file
   and an elided statement. So a Strategist auditing g10944 had to go
   find `.drafts/backward_g10944_patch.lean` to learn that a `j = 0`
   counterexample had refuted it, and four hours later another one
   asked about a shelved goal and was told nothing about the shelf
   (11:56, 13:47).
2. A grep truncated near source line 339 answered "Continue from line
   4 with `lines`" — a line nobody asked about, in a parameter grep
   does not take (16:12).
3. A refused / over-budget raw read came back `isError=false`, so the
   flag alone could not tell a refusal from file content (16:54).

All sqlite + tmp files; no Lean, no spawns.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from Tooling.knowledge import workspace_query as wq
from Tooling.state import db


# ---------------------------------------------------------------------
# 1. `decl` carries the goal's own reason
# ---------------------------------------------------------------------

@pytest.fixture
def ws(tmp_path: Path) -> Path:
    """A workspace with one problem and a stub per goal, so `decl`
    resolves a real signature the way the live tool does."""
    (tmp_path / "Tooling").mkdir()
    (tmp_path / "Problems" / "Cat" / "a" / "proofs").mkdir(parents=True)
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
                 " VALUES ('Cat.a', ?, 1)", (db.now(),))
    conn.commit()
    conn.close()
    return tmp_path


def _here(ws: Path) -> Path:
    return ws / "Problems" / "Cat" / "a"


def _goal(ws: Path, slug: str, status: str = "open") -> int:
    rel = f"Problems/Cat/a/proofs/L_{slug}.lean"
    (ws / rel).write_text(f"import Mathlib\ntheorem {slug} : True := by\n"
                          f"  trivial\n", encoding="utf-8")
    conn = db.connect(ws / "asterism.db")
    gid = db.insert_goal(conn, problem="Cat.a", slug=slug, lean_path=rel,
                         statement="True", origin="backward", status=status)
    conn.commit()
    conn.close()
    return int(gid)


def _dead(ws: Path, gid: int, *, reason: str, detail: str = "",
          proposal: str = "") -> None:
    conn = db.connect(ws / "asterism.db")
    conn.execute("INSERT INTO pipelines (id, kind, target_id, target_kind,"
                 " status, started_at, finished_at)"
                 " VALUES (?, 'Backward', ?, 'Goal', 'failed', ?, ?)",
                 (f"pid{gid}{reason}", str(gid), db.now(), db.now()))
    db.record_dead_attempt(conn, target_id=gid, target_kind="Goal",
                           pipeline_id=f"pid{gid}{reason}",
                           failure_reason=reason, failure_detail=detail,
                           proposal_md=proposal)
    conn.commit()
    conn.close()


def _confirm_shelve(ws: Path, gid: int, brief: str) -> None:
    conn = db.connect(ws / "asterism.db")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, outcome,"
        " created_at, updated_at)"
        " VALUES ('Cat.a', 0, 'routine', 'ConfirmShelve', ?, ?, 'success',"
        " ?, ?)", (gid, brief, db.now(), db.now()))
    conn.commit()
    conn.close()


def test_a_shelved_decl_carries_the_park_reason_and_the_last_failure(ws):
    """13:47 — `inspect([{decl: "..."}])` on a shelved goal returned
    only status, file and an elided statement, "with no shelving/death
    reason". 11:56 — the same for a pending-review goal, whose decisive
    counterexample then lived only in a draft file. Both facts are rows
    in this run's own tables."""
    gid = _goal(ws, "four_target_clean_action_normal_form", status="shelved")
    _confirm_shelve(ws, gid, "Park it until punctured_boolean lands as a "
                             "standalone declaration.")
    _dead(ws, gid, reason="return_to_nl",
          proposal="s27322's j = 0, M = 3 counterexample refutes it.")
    out = wq.run_queries(
        [{"decl": "four_target_clean_action_normal_form"}], cwd=_here(ws))
    assert "why this goal is not proved" in out, out
    assert "ConfirmShelve" in out
    assert "punctured_boolean lands as a standalone declaration" in out
    assert "return_to_nl" in out
    assert "j = 0, M = 3 counterexample" in out


def test_a_pending_review_decl_carries_the_decline_text(ws):
    gid = _goal(ws, "arm_frequency", status="pending_strategist_review")
    _dead(ws, gid, reason="agent_declined",
          proposal="the locked signature drops (hUW : ...) that Step 3 needs")
    out = wq.run_queries([{"decl": "arm_frequency"}], cwd=_here(ws))
    assert "why this goal is not proved" in out, out
    assert "agent_declined" in out
    assert "Step 3 needs" in out


def test_an_unsettled_decl_with_nothing_on_record_says_so(ws):
    """Silence is the failure this fixes; an empty reason block would
    reproduce it one layer down."""
    _goal(ws, "quiet_one", status="shelved")
    out = wq.run_queries([{"decl": "quiet_one"}], cwd=_here(ws))
    assert "nothing on record" in out, out
    assert "no park reason" in out


def test_an_alive_or_proved_decl_carries_no_reason_block(ws):
    _goal(ws, "still_open", status="open")
    _goal(ws, "already_done", status="proved")
    for slug in ("still_open", "already_done"):
        out = wq.run_queries([{"decl": slug}], cwd=_here(ws))
        assert "why this goal is not proved" not in out, out


def test_a_long_reason_keeps_both_ends_and_names_what_went(ws):
    """An agent puts the ask LAST; a head-only cut hides it. Same rule
    the Strategist's decline digest already follows."""
    gid = _goal(ws, "verbose_one", status="shelved")
    _dead(ws, gid, reason="parent_needs_fix",
          proposal="HEAD_MARKER " + ("filler " * 900) + " TAIL_MARKER")
    out = wq.run_queries([{"decl": "verbose_one"}], cwd=_here(ws))
    assert "HEAD_MARKER" in out and "TAIL_MARKER" in out, out
    assert "chars elided" in out


def test_the_reason_block_does_not_blow_the_query_budget(ws):
    """Six substring matches, each with a long post-mortem, must still
    leave room for the signatures — a shortlist is for picking a name,
    not for reading six post-mortems."""
    for n in range(6):
        gid = _goal(ws, f"shared_name_{n}", status="shelved")
        _dead(ws, gid, reason="no_progress", proposal="x" * 4000)
    out = wq.run_queries([{"decl": "shared_name"}], cwd=_here(ws))
    assert "truncated at" not in out, out


# ---------------------------------------------------------------------
# 2. a truncated answer names the last line it actually delivered
# ---------------------------------------------------------------------

def _grep_file(tmp_path: Path) -> None:
    (tmp_path / "Tooling").mkdir(exist_ok=True)
    body = [f"-- filler {n}" for n in range(1, 301)]
    body += [f"theorem t{n} : True := trivial  " + "x" * 40
             for n in range(301, 401)]
    (tmp_path / "big.lean").write_text("\n".join(body) + "\n",
                                       encoding="utf-8")


def test_a_truncated_grep_resumes_from_the_last_hit_it_delivered(tmp_path):
    """16:12 — truncated near source line 339, the footer said "Continue
    from line 4 with lines". The sniff read `ln[:5]`, which on a
    context block (`"  " + f"{n:>5}" + "  "`) slices into a three-digit
    number and yields its first digit; and `lines` is not even a
    continuation grep accepts. Grep resumes by `after`."""
    _grep_file(tmp_path)
    out = wq.run_queries([{"grep": "theorem", "in": "big.lean",
                           "context": 1, "max": 400}],
                         cwd=tmp_path, per_query_chars=3000)
    assert "Continue from line" not in out, out
    m = re.search(r'after: "([^"]+)"', out)
    assert m, out
    rel, _, line = m.group(1).rpartition(":")
    assert rel == "big.lean" and int(line) > 300, m.group(1)
    # and it must be a line the reader HAS: the next call picks up after
    # it with no hit lost.
    assert f"big.lean:{int(line)}:" in out
    out2 = wq.run_queries([{"grep": "theorem", "in": "big.lean",
                            "after": m.group(1)}], cwd=tmp_path)
    assert f"big.lean:{int(line) + 1}:" in out2, out2


def test_a_truncated_read_resumes_at_the_first_line_it_did_not_finish(
        tmp_path):
    """Same rule on the sibling path: the cut lands mid-line, so the
    last row is a line the reader has only part of. Naming the row
    AFTER it drops that tail silently — truncation is a view, never a
    loss."""
    (tmp_path / "Tooling").mkdir(exist_ok=True)
    (tmp_path / "doc.md").write_text(
        "".join(f"body {'y' * 60} END{n}\n" for n in range(1, 400)),
        encoding="utf-8")
    out = wq.run_queries([{"read": "doc.md", "lines": "1-399"}],
                         cwd=tmp_path, per_query_chars=3000)
    m = re.search(r'"lines": "(\d+)-"', out)
    assert m, out
    resume = int(m.group(1))
    kept = out.split("… [1] truncated")[0]
    assert f"END{resume}\n" not in kept, "resume names a line already whole"
    assert f"END{resume - 1}\n" in kept, kept[-200:]


# ---------------------------------------------------------------------
# 3. a refusal is an error on the MCP result, not content
# ---------------------------------------------------------------------

def _call_inspect(queries: list, cwd: Path):
    from Tooling.knowledge import mcp_tools
    from Tooling.llm.spawn_guard import TOOL_CWD_CONTEXT
    token = TOOL_CWD_CONTEXT.set(str(cwd))
    try:
        return asyncio.run(mcp_tools.mcp._tool_manager.call_tool(
            "inspect", {"queries": queries}, context=None,
            convert_result=True))
    finally:
        TOOL_CWD_CONTEXT.reset(token)


def _is_error(result) -> bool:
    return bool(getattr(result, "isError", False))


def _text_of(result) -> str:
    blocks = getattr(result, "content", result)
    if isinstance(blocks, tuple):
        blocks = blocks[0]
    return "\n".join(getattr(b, "text", "") or "" for b in blocks)


def test_an_over_budget_raw_read_is_flagged_as_an_error(tmp_path):
    """16:54 — "raw read is 12,794 chars — over the 12,000-char reply
    budget" came back with `isError=false`, so an agent checking the
    flag alone reads the refusal as the file."""
    (tmp_path / "Tooling").mkdir(exist_ok=True)
    (tmp_path / "report.md").write_text("z" * 13_000, encoding="utf-8")
    res = _call_inspect([{"read": "report.md", "raw": True}], tmp_path)
    assert _is_error(res), _text_of(res)
    assert "over the" in _text_of(res), _text_of(res)


def test_a_refused_read_keeps_its_whole_answer_while_flagging_the_error(
        tmp_path):
    """The flag must not cost the text: what the refusal SAYS is the way
    back in."""
    (tmp_path / "Tooling").mkdir(exist_ok=True)
    (tmp_path / "big.md").write_text(
        "".join(f"## S{n}\n{'body ' * 20}\n" for n in range(200)),
        encoding="utf-8")
    res = _call_inspect([{"read": "big.md"}], tmp_path)
    assert _is_error(res)
    body = _text_of(res)
    # "one ANSWER's budget", not "one reply's": the 12,000 cap is
    # per query and a reply carries 30,000, and calling the smaller
    # number the reply budget is exactly the contradiction four
    # adversaries filed on 2026-09-07/08.
    assert "more than one answer's" in body, body
    assert "outline" in body


def test_a_missing_file_is_an_error_and_reads_the_same_as_before(tmp_path):
    (tmp_path / "Tooling").mkdir(exist_ok=True)
    res = _call_inspect([{"read": "nope.md"}], tmp_path)
    assert _is_error(res)
    body = _text_of(res)
    assert "no file at" in body, body
    assert "raw read refused" not in body and "not content" not in body


def test_a_batch_that_delivered_content_is_not_an_error(tmp_path):
    """One refused query among several must not stamp the whole call:
    the other answers are real content the agent has to keep."""
    (tmp_path / "Tooling").mkdir(exist_ok=True)
    (tmp_path / "ok.md").write_text("# T\nhello\n", encoding="utf-8")
    res = _call_inspect([{"read": "nope.md"}, {"read": "ok.md"}], tmp_path)
    assert not _is_error(res), _text_of(res)
    assert "hello" in _text_of(res)


def test_a_plain_answer_is_not_an_error(tmp_path):
    (tmp_path / "Tooling").mkdir(exist_ok=True)
    (tmp_path / "ok.md").write_text("# T\nhello\n", encoding="utf-8")
    assert not _is_error(_call_inspect([{"read": "ok.md"}], tmp_path))
    # a zero-hit grep is a real answer, not a failure (the framework
    # spent a whole fix teaching agents exactly that)
    assert not _is_error(
        _call_inspect([{"grep": "nothing_here", "in": "ok.md"}], tmp_path))


def test_the_public_outline_never_leaks_the_not_content_marker(tmp_path):
    """`outline()` is the framework's own call — the Adversary's dossier
    renders it into a prompt — so the in-band marker `run_queries`
    strips must never reach it."""
    out = "\n".join(wq.outline(tmp_path / "absent.md"))
    assert "no file at" in out
    assert not out.startswith(wq.NOT_CONTENT)
