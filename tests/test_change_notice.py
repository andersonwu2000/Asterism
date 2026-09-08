"""`## Changed since you started` — the trailer every MCP tool carries.

Fast by construction: a workspace of empty files under `tmp_path` and a
two-table sqlite file. No daemon, no gateway, no Lean.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from types import SimpleNamespace

import pytest

from Tooling.agent import change_notice


PROBLEM = "Test.p1"


def _write(path, text: str, *, mtime: "float | None" = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    # Explicit mtime: a second edit within the filesystem's mtime
    # granularity would otherwise be invisible to the stat pre-filter,
    # and this suite must not depend on how coarse that is.
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _workspace(tmp_path):
    ws = tmp_path / "ws"
    pdir = ws / "Problems" / "Test" / "p1"
    _write(pdir / "problem.json",
           json.dumps({"problem": PROBLEM, "charter": "prove it"}),
           mtime=1_700_000_000)
    _write(ws / "Problems" / "Test" / "_docs" / "user" / "notes.md",
           "# notes\n", mtime=1_700_000_000)
    _db(ws)
    return ws


def _db(ws):
    """The two tables the notice reads. A real file, so the read goes
    through the same `?mode=ro` URI production uses."""
    path = ws / "asterism.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE theory_documents (id INTEGER PRIMARY KEY,"
        " problem TEXT, path TEXT, status TEXT);"
        "CREATE TABLE goals (id INTEGER PRIMARY KEY, problem TEXT,"
        " slug TEXT, lean_path TEXT, status TEXT);")
    conn.commit()
    conn.close()
    return path


def _notice(ws):
    return change_notice.ChangeNotice(ws, PROBLEM)


# ── 1. nothing changed ───────────────────────────────────────────────

def test_no_change_no_trailer(tmp_path):
    ws = _workspace(tmp_path)
    notice = _notice(ws)
    assert notice.trailer() == ""
    assert notice.trailer() == ""


# ── 2/3. an owner file, edited once and then again ───────────────────

def test_owner_edit_reported_once_then_silent(tmp_path):
    ws = _workspace(tmp_path)
    notice = _notice(ws)
    doc = ws / "Problems" / "Test" / "_docs" / "user" / "notes.md"
    # 2026-01-01 16:40Z — pinned so the rendered stamp is checkable.
    _write(doc, "# notes\nowner candidate\n", mtime=1_767_285_600)

    out = notice.trailer()
    assert out.startswith("\n\n## Changed since you started\n")
    assert ("- owner edited `Problems/Test/_docs/user/notes.md` (16:40Z)"
            in out)
    assert out.endswith(
        '\nRead what bears on your task: inspect [{"read":"<path>"}].')
    assert out.count("- owner edited") == 1
    # once, and only once
    assert notice.trailer() == ""


def test_second_edit_reported_again(tmp_path):
    ws = _workspace(tmp_path)
    notice = _notice(ws)
    doc = ws / "Problems" / "Test" / "_docs" / "user" / "notes.md"
    _write(doc, "one\n", mtime=1_767_285_600)
    assert "- owner edited" in notice.trailer()
    _write(doc, "two\n", mtime=1_767_285_660)
    again = notice.trailer()
    assert "- owner edited `Problems/Test/_docs/user/notes.md` (16:41Z)" \
        in again


def test_touch_without_content_change_is_not_an_edit(tmp_path):
    ws = _workspace(tmp_path)
    notice = _notice(ws)
    doc = ws / "Problems" / "Test" / "_docs" / "user" / "notes.md"
    _write(doc, "# notes\n", mtime=1_767_285_600)   # same bytes, new mtime
    assert notice.trailer() == ""


def test_problem_json_is_an_owner_surface(tmp_path):
    ws = _workspace(tmp_path)
    notice = _notice(ws)
    _write(ws / "Problems" / "Test" / "p1" / "problem.json",
           json.dumps({"problem": PROBLEM, "charter": "prove it, but "
                                                      "only for n > 2"}),
           mtime=1_767_285_600)
    assert "- owner edited `Problems/Test/p1/problem.json` (16:40Z)" \
        in notice.trailer()


def test_a_new_user_document_counts(tmp_path):
    ws = _workspace(tmp_path)
    notice = _notice(ws)
    _write(ws / "Problems" / "Test" / "_docs" / "user" / "fresh.md",
           "new\n", mtime=1_767_285_600)
    assert "- owner edited `Problems/Test/_docs/user/fresh.md`" \
        in notice.trailer()


# ── 4. the machine-settled facts ─────────────────────────────────────

def test_accepted_document_and_proved_brick(tmp_path):
    ws = _workspace(tmp_path)
    notice = _notice(ws)
    conn = sqlite3.connect(ws / "asterism.db")
    conn.executescript(
        "INSERT INTO theory_documents VALUES"
        " (1, 'Test.p1', 'Problems/Test/_docs/agent/g691_x.md', 'accepted'),"
        " (2, 'Test.p1', 'Problems/Test/_docs/agent/g692_x.md', 'rejected'),"
        " (3, 'Other.p9', 'Problems/Other/_docs/agent/nope.md', 'accepted');"
        "INSERT INTO goals VALUES"
        " (10, 'Test.p1', 'shell_closure',"
        "  'Problems/Test/p1/proofs/L_shell_closure.lean', 'proved'),"
        " (11, 'Test.p1', 'open_one',"
        "  'Problems/Test/p1/proofs/L_open_one.lean', 'open'),"
        " (12, 'Other.p9', 'elsewhere',"
        "  'Problems/Other/p9/proofs/L_elsewhere.lean', 'proved');")
    conn.commit()
    conn.close()

    out = notice.trailer()
    assert ("- theory document accepted: "
            "`Problems/Test/_docs/agent/g691_x.md`") in out
    # The SLUG (what `inspect decl` resolves) and the proof file (what
    # `inspect read` resolves) — never the `L_`-prefixed file stem, and
    # no CATALOG.md, because this spawn has no attempts dir with one.
    assert ("- brick proved: `shell_closure` — "
            "`Problems/Test/p1/proofs/L_shell_closure.lean`") in out
    assert "CATALOG.md" not in out
    # scoped to this problem, and to what is settled
    assert "g692" not in out and "Other" not in out and "open_one" not in out
    assert notice.trailer() == ""


def _land_brick(ws, *, slug="shell_closure", gid=10):
    conn = sqlite3.connect(ws / "asterism.db")
    conn.execute(
        "INSERT INTO goals VALUES (?, ?, ?, ?, 'proved')",
        (gid, PROBLEM, slug, f"Problems/Test/p1/proofs/L_{slug}.lean"))
    conn.commit()
    conn.close()


def test_the_brick_line_resolves_by_decl_and_by_read(tmp_path):
    """The 2026-09-07 fleet's most-filed line: eight Theorists were sent
    to `L_<slug>` (which `decl` cannot resolve — the lookup reads
    `goals.slug`, and the `L_` is a filename convention) and to a
    CATALOG.md a fresh pure-NL problem never writes."""
    ws = _workspace(tmp_path)
    notice = _notice(ws)
    _land_brick(ws)
    out = notice.trailer()
    # what `inspect({"decl": ...})` matches, verbatim
    assert "`shell_closure`" in out
    assert "L_shell_closure`" not in out
    # what `inspect({"read": ...})` resolves, and it is on disk
    assert "`Problems/Test/p1/proofs/L_shell_closure.lean`" in out


def test_a_root_brick_keeps_the_name_its_wrapper_declares(tmp_path):
    ws = _workspace(tmp_path)
    notice = _notice(ws)
    conn = sqlite3.connect(ws / "asterism.db")
    conn.execute("INSERT INTO goals VALUES (7, ?, 'main',"
                 " 'Problems/Test/p1/Root.lean', 'proved')", (PROBLEM,))
    conn.commit()
    conn.close()
    out = notice.trailer()
    assert ("- brick proved: `main` — `Problems/Test/p1/Root.lean`") in out


def test_catalog_named_only_when_one_is_beside_the_reader(tmp_path):
    ws = _workspace(tmp_path)
    attempts = ws / ".attempts" / "1234"
    attempts.mkdir(parents=True)
    notice = change_notice.ChangeNotice(ws, PROBLEM, catalog_dir=attempts)
    _land_brick(ws)
    # No companion yet — a fresh problem writes none, so nothing points
    # the reader at one.
    assert "CATALOG.md" not in notice.trailer()

    _write(attempts / "CATALOG.md", "# Proved catalog\n")
    _land_brick(ws, slug="second_one", gid=11)
    out = notice.trailer()
    assert "- brick proved: `second_one`" in out
    assert f"(also in `{(attempts / 'CATALOG.md').as_posix()}`)" in out


def test_missing_tables_are_not_an_error(tmp_path):
    ws = _workspace(tmp_path)
    (ws / "asterism.db").unlink()
    sqlite3.connect(ws / "asterism.db").close()      # empty schema
    notice = _notice(ws)
    assert notice.trailer() == ""


# ── 5. the cap, and what it defers ───────────────────────────────────

def test_cap_defers_the_rest_to_the_next_call(tmp_path):
    ws = _workspace(tmp_path)
    notice = _notice(ws)
    shelf = ws / "Problems" / "Test" / "_docs" / "user"
    for i in range(15):
        _write(shelf / f"doc{i:02d}.md", f"body {i}\n", mtime=1_767_285_600)

    first = notice.trailer()
    assert first.count("\n- ") == change_notice.MAX_LINES == 12
    assert first.endswith(
        '\nRead what bears on your task: inspect [{"read":"<path>"}].')
    second = notice.trailer()
    assert second.count("\n- ") == 3
    assert notice.trailer() == ""


# ── 6. both servers append it ────────────────────────────────────────

class _Stub:
    TEXT = "\n\n## Changed since you started\n- owner edited `x` (16:40Z)\n"

    def trailer(self):
        return self.TEXT


def _call(server, name, args):
    return asyncio.run(server._tool_manager.call_tool(
        name, args, convert_result=True))


def _text_of(result):
    if isinstance(result, tuple):
        result = result[0]
    if isinstance(result, str):
        return result
    return "".join(getattr(b, "text", "") for b in result)


def test_asterism_tools_server_appends_it(monkeypatch):
    from Tooling.knowledge import mcp_tools
    from Tooling.llm import spawn_guard
    monkeypatch.setenv(spawn_guard.PROBLEM_ENV, PROBLEM)
    monkeypatch.setattr(change_notice, "for_spawn",
                        lambda *a, **k: _Stub())
    out = _text_of(_call(mcp_tools.mcp, "validate_json", {"text": "{}"}))
    assert out.startswith("OK: 0 top-level key(s)")
    assert out.endswith(_Stub.TEXT)


def test_asterism_tools_raw_read_is_left_byte_faithful(monkeypatch):
    """A `raw` answer is content the agent writes back — appending to it
    would put the notice INSIDE the file."""
    from Tooling.knowledge import mcp_tools
    from Tooling.llm import spawn_guard
    monkeypatch.setenv(spawn_guard.PROBLEM_ENV, PROBLEM)
    monkeypatch.setattr(change_notice, "for_spawn",
                        lambda *a, **k: _Stub())
    monkeypatch.setattr(mcp_tools, "_workspace_root", lambda: None)
    assert mcp_tools._suppress_change_notice(
        "inspect", {"queries": [{"read": "patch.lean", "raw": True}]})
    assert not mcp_tools._suppress_change_notice(
        "inspect", {"queries": [{"read": "patch.lean"}]})
    assert not mcp_tools._suppress_change_notice("validate_json", {})


def test_lsp_gateway_server_appends_it(monkeypatch, tmp_path):
    from Tooling.lsp import gateway
    meta = SimpleNamespace(workspace=tmp_path, problem=PROBLEM)
    monkeypatch.setattr(change_notice, "for_spawn",
                        lambda *a, **k: _Stub())
    monkeypatch.setattr(gateway, "_current_session", lambda: meta)
    token = gateway._session_ctx.set("tok")
    try:
        out = _text_of(_call(gateway.mcp, "goal_at", {}))
    finally:
        gateway._session_ctx.reset(token)
    assert "the parameters are `line`" in out
    assert out.endswith(_Stub.TEXT)


def test_asterism_tools_end_to_end_with_the_real_watcher(monkeypatch,
                                                         tmp_path):
    """No stub: the server's own resolver, a real workspace, a real
    edit — the whole path an agent's tool call takes."""
    from Tooling.knowledge import mcp_tools
    from Tooling.llm import spawn_guard
    ws = _workspace(tmp_path)
    monkeypatch.setenv(spawn_guard.PROBLEM_ENV, PROBLEM)
    monkeypatch.setattr(mcp_tools, "_workspace_root", lambda: ws)
    change_notice._WATCHERS.clear()
    try:
        mcp_tools._prime_change_notice()          # the baseline
        assert _text_of(_call(mcp_tools.mcp, "validate_json",
                              {"text": "{}"})) == "OK: 0 top-level key(s)"
        _write(ws / "Problems" / "Test" / "_docs" / "user" / "notes.md",
               "the owner changed their mind\n", mtime=1_767_285_600)
        out = _text_of(_call(mcp_tools.mcp, "validate_json", {"text": "{}"}))
        assert out == (
            "OK: 0 top-level key(s)\n\n## Changed since you started\n"
            "- owner edited `Problems/Test/_docs/user/notes.md` (16:40Z)\n"
            'Read what bears on your task: inspect [{"read":"<path>"}].')
        # ...and once only
        assert _text_of(_call(mcp_tools.mcp, "validate_json",
                              {"text": "{}"})) == "OK: 0 top-level key(s)"
    finally:
        change_notice._WATCHERS.clear()


def test_no_news_leaves_the_result_untouched(monkeypatch):
    from Tooling.knowledge import mcp_tools
    monkeypatch.setattr(change_notice, "for_spawn", lambda *a, **k: None)
    out = _text_of(_call(mcp_tools.mcp, "validate_json", {"text": "{}"}))
    assert out == "OK: 0 top-level key(s)"


@pytest.mark.parametrize("result", ["answer", ["not a block"]])
def test_append_never_loses_the_answer(result):
    out = change_notice.append(result, "\n\nnews")
    assert "answer" in str(out) or "not a block" in str(out)
