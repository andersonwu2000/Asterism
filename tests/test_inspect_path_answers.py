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


def _project_workspace(tmp_path: Path) -> Path:
    """A workspace `workspace_of` can actually recognise (it wants both
    `Problems` and `Tooling`), with the live shape: a problem nested
    under its Project, and the Project's document root beside it."""
    (tmp_path / "Tooling").mkdir()
    cwd = tmp_path / "Problems" / "Combinatorics" / "union_closed"
    cwd.mkdir(parents=True)
    note = (tmp_path / "Problems" / "Combinatorics" / "_docs" / "user"
            / "split_note.md")
    note.parent.mkdir(parents=True)
    note.write_text("# SPLIT\n\nthe abundance cut\n", encoding="utf-8")
    return cwd


def test_a_workspace_relative_path_reaches_the_workspace_root(
        tmp_path: Path):
    """The framework prints workspace-relative paths at its agents —
    `.lake/packages/mathlib`, `Library/`, and since HID §3.6 the owner's
    notes under `Problems/<project>/_docs/user/` — while every spawn's
    cwd is its problem dir, two levels down. Only `.lake` was anchored,
    by name, so the Context could point at a file `inspect` then swore
    was not there. The workspace is the second anchor for ALL of them."""
    cwd = _project_workspace(tmp_path)

    out = wq.run_queries(
        [{"read": "Problems/Combinatorics/_docs/user/split_note.md"}],
        cwd=cwd, per_query_chars=2000)

    assert "the abundance cut" in out, out
    assert "no file at" not in out, out


def test_the_workspace_anchor_is_not_a_hole_in_the_read_fence(
        tmp_path: Path):
    """Anchoring is resolution, not a grant: what the anchor reaches,
    `read_deny_roots` still fences. A sibling Project's problem now
    RESOLVES from a workspace-relative path — and must come back as the
    operator-private refusal, never as its contents."""
    cwd = _project_workspace(tmp_path)
    foreign = tmp_path / "Problems" / "Erdos" / "p1"
    foreign.mkdir(parents=True)
    (foreign / "Root.lean").write_text("theorem secret : True := trivial\n",
                                       encoding="utf-8")

    out = wq.run_queries([{"read": "Problems/Erdos/p1/Root.lean"}],
                         cwd=cwd, per_query_chars=2000)

    assert "secret" not in out, out
    assert "operator-private" in out, out


# ── a same-named file elsewhere is NAMED, not prescribed ─────────────

def test_a_missing_report_is_not_answered_with_another_rounds_report(
        tmp_path: Path, monkeypatch):
    """The 2026-09-08 field reading: a reviewer asked for
    `…/54c1fb01…/review/r2/report.md` and `inspect` answered "but a file
    of that name is at …/4fea01b9…/review/r1/report.md — use that path"
    — an imperative naming another attempt's earlier round. The
    basename search drops every path segment that identifies the
    document, and `review/r2` is exactly such a segment.

    The place asked for is real; the file simply is not in it. So the
    other file is named as what it is, and citing it is offered as a
    decision the reader makes."""
    cwd, _attempts = _workspace(tmp_path, monkeypatch)
    mine = cwd / "review" / "r2"
    mine.mkdir(parents=True)                      # my round exists…
    other = cwd / "other_attempt" / "review" / "r1"
    other.mkdir(parents=True)
    (other / "report.md").write_text("someone else's round\n",
                                     encoding="utf-8")

    out = wq.run_queries([{"read": "review/r2/report.md"}], cwd=cwd)
    assert "no file at" in out
    assert "different attempt/round" in out
    assert "cite it only if you mean that one" in out
    assert "use that path" not in out
    # named, so the reader can still act on it deliberately
    assert "r1" in out and "report.md" in out


def test_a_same_named_file_under_the_asked_for_dirs_is_still_the_answer(
        tmp_path: Path, monkeypatch):
    """The suffix case: the spec's directories ARE where the hit sits
    (the spawn's other root), so nothing about the document's identity
    was dropped and the pointer stands."""
    cwd, attempts = _workspace(tmp_path, monkeypatch)
    (attempts / "review" / "r2").mkdir(parents=True)
    (attempts / "review" / "r2" / "report.md").write_text(
        "mine\n", encoding="utf-8")
    out = wq.run_queries([{"read": "review/r2/report.md"}], cwd=cwd)
    # resolution finds it outright, or the hint prescribes it — either
    # way the reader is not sent to another round
    assert "different attempt/round" not in out
    assert "mine" in out or "use that path" in out


def test_a_mistyped_directory_still_gets_the_file_it_meant(
        tmp_path: Path, monkeypatch):
    """`prooofs/L_a.lean` names a directory that does not exist — one
    document, misspelled — and the file of that name is what was meant
    (2026-08-15). The identity rule must not eat this case."""
    cwd, _attempts = _workspace(tmp_path, monkeypatch)
    (cwd / "proofs").mkdir()
    (cwd / "proofs" / "L_a.lean").write_text("theorem a : True\n",
                                             encoding="utf-8")
    out = wq.run_queries([{"read": "prooofs/L_a.lean"}], cwd=cwd)
    assert "use that path" in out
    assert "different attempt/round" not in out


# ── a glob that matched nothing says so ──────────────────────────────

def test_a_glob_with_no_hits_says_it_was_a_glob_and_lists_the_dir(
        tmp_path: Path, monkeypatch):
    """`_glob_split` cuts the pattern off before the miss is described,
    so the diagnostic was handed the glob-free PREFIX — a directory,
    every time — and answered "that path IS a directory and it is EMPTY
    — the path was used exactly as given". False twice: the path was
    not used as given, and an EMPTY verdict on a directory full of
    files is the opposite of what the reader needed to know."""
    cwd, _attempts = _workspace(tmp_path, monkeypatch)
    (cwd / "proofs").mkdir()
    (cwd / "proofs" / "L_a.lean").write_text("theorem a : True\n",
                                             encoding="utf-8")

    out = wq.run_queries([{"grep": "theorem", "in": "proofs/*.rs"}], cwd=cwd)
    assert "matched 0 files" in out
    assert "glob" in out
    assert "L_a.lean" in out                      # what IS there
    assert "used exactly as given" not in out
    assert "is EMPTY" not in out


def test_a_glob_over_an_empty_directory_says_the_directory_is_empty(
        tmp_path: Path, monkeypatch):
    cwd, _attempts = _workspace(tmp_path, monkeypatch)
    (cwd / "proofs").mkdir()
    out = wq.run_queries([{"grep": "theorem", "in": "proofs/*.lean"}], cwd=cwd)
    assert "matched 0 files" in out
    assert "is EMPTY" in out


def test_a_plain_directory_miss_keeps_its_own_answer(
        tmp_path: Path, monkeypatch):
    """The non-glob spelling is untouched: an empty directory named
    directly still gets the sentence that settles it."""
    cwd, _attempts = _workspace(tmp_path, monkeypatch)
    (cwd / "proofs").mkdir()
    out = wq.run_queries([{"grep": "theorem", "in": "proofs"}], cwd=cwd)
    assert "used exactly as given" in out
    assert "matched 0 files" not in out
