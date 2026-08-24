"""A path the agent got wrong must come back with the path that works.

Two residual complaints from the 08-13/14 feedback, both the same
shape: the tool knew what was wrong and answered with something the
agent could not act on.

The third complaint in that cluster — one 8000-char budget shared
across a batch, so the later queries in a call silently lost answers —
was already fixed; the budget is per query with a floor, and
`run_queries`' docstring records it.
"""
from __future__ import annotations

from pathlib import Path

from Tooling.knowledge import workspace_query as wq


def _workspace(tmp_path: Path, monkeypatch=None) -> "tuple[Path, Path]":
    """The real shape: the spawn is launched in its problem dir, and its
    briefing files live in the attempts dir on the other branch. With
    `monkeypatch`, that attempts dir is declared as THIS spawn's own —
    the way production does, through `ASTERISM_SPAWN_WRITE_ROOTS`."""
    (tmp_path / "Problems" / "P").mkdir(parents=True)
    attempts = tmp_path / ".attempts" / "pid1"
    attempts.mkdir(parents=True)
    if monkeypatch is not None:
        monkeypatch.setenv("ASTERISM_SPAWN_WRITE_ROOTS", str(attempts))
    return tmp_path / "Problems" / "P", attempts


def test_a_relative_path_reaches_my_own_attempt_dir(tmp_path: Path,
                                                    monkeypatch):
    """A spawn works in TWO directories and a relative path resolved
    against one. The Adversary's `inspect(in="CATALOG.md")` failed and
    the hint walked up to the workspace root and listed the repo — true,
    useless, and a round trip.

    The first fix (2026-08-13) answered with a hint naming the file, but
    found it by scanning EVERY attempt dir, so under concurrency it
    named a sibling spawn's copy (2026-08-16). Resolving against this
    spawn's own attempt dir removes the round trip entirely: the query
    just works, and it works on the right file."""
    cwd, attempts = _workspace(tmp_path, monkeypatch)
    (attempts / "CATALOG.md").write_text("uc_634 is here\n",
                                         encoding="utf-8")

    out = wq.run_queries([{"grep": "uc_634", "in": "CATALOG.md"}],
                         cwd=cwd, per_query_chars=400)

    assert "uc_634 is here" in out, out
    assert "no file" not in out and "nothing to search" not in out


def test_an_absolute_find_pattern_is_answered_not_refused(tmp_path: Path):
    """`find` with an absolute pattern is the natural phrasing when the
    only path you were handed is absolute — the Adversary's projection
    is. `rglob` answers it with `NotImplementedError: Non-relative
    patterns are unsupported`, a Python type name handed to an agent as
    if it were advice. The request is unambiguous; honour it."""
    cwd, _ = _workspace(tmp_path)
    (cwd / "proofs").mkdir()
    (cwd / "proofs" / "L_a.lean").write_text("x\n", encoding="utf-8")

    out = wq.run_queries(
        [{"find": str(cwd / "proofs" / "*.lean")}], cwd=cwd, per_query_chars=400)

    assert "NotImplementedError" not in out, out
    assert "L_a.lean" in out, out


def test_a_genuinely_missing_file_still_says_what_is_there(tmp_path: Path):
    """The name-the-file hint must not swallow the older one: when
    nothing of that name exists anywhere, the agent still gets the
    directory listing that saves it an `ls`."""
    cwd, _ = _workspace(tmp_path)
    (cwd / "real.lean").write_text("x\n", encoding="utf-8")

    out = wq.run_queries([{"grep": "x", "in": "nope.md"}],
                         cwd=cwd, per_query_chars=400)

    assert "nearest existing directory" in out, out
    assert "real.lean" in out, out


def test_basename_hint_never_names_a_foreign_attempt(tmp_path: Path,
                                                     monkeypatch):
    """Under the shim the tools run in-process, so `cwd` can be the
    REPO ROOT — and the old rglob walked every attempt from it:
    `.attempts/` sorts before `Problems/`, so a FOREIGN spawn's TREE.md
    answered a presearch's bare read (both fleets, 2026-08-24). The
    walk now prunes `.attempts` (a heavy dir) from broad roots; the
    spawn's OWN attempt dir is still covered as its own root."""
    cwd, attempts = _workspace(tmp_path, monkeypatch)
    foreign = tmp_path / ".attempts" / "aaa-foreign" / "adversary" / "r1"
    foreign.mkdir(parents=True)
    (foreign / "TREE.md").write_text("FOREIGN TREE\n", encoding="utf-8")
    (tmp_path / "Problems" / "P" / "TREE.md").write_text(
        "MY TREE\n", encoding="utf-8")

    # repo-root cwd (the shim's): the answer must be the problem's
    # file, never the foreign attempt's — even though the foreign path
    # sorts first
    found = wq._find_by_basename("TREE.md", tmp_path)
    assert found is not None
    assert "aaa-foreign" not in str(found)
    assert found == tmp_path / "Problems" / "P" / "TREE.md"

    # the spawn's own attempt dir is still searchable
    (attempts / "Context.md").write_text("mine\n", encoding="utf-8")
    own_hit = wq._find_by_basename("Context.md", tmp_path)
    assert own_hit == attempts / "Context.md"


def test_run_queries_cwd_falls_back_to_the_request_context(
        tmp_path: Path, monkeypatch):
    """The shim carries the spawn's problem dir per request
    (TOOL_CWD_CONTEXT via the URL /c/ segment); run_queries must use it
    when no explicit cwd is passed — Path.cwd() is the SHIM's cwd, not
    the spawn's."""
    from Tooling.llm.spawn_guard import TOOL_CWD_CONTEXT
    cwd, _attempts = _workspace(tmp_path, monkeypatch)
    (cwd / "TREE.md").write_text("ctx tree\n", encoding="utf-8")
    token = TOOL_CWD_CONTEXT.set(str(cwd))
    try:
        out = wq.run_queries([{"read": "TREE.md"}], per_query_chars=400)
    finally:
        TOOL_CWD_CONTEXT.reset(token)
    assert "ctx tree" in out, out
