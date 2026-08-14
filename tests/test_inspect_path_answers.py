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


def _workspace(tmp_path: Path) -> "tuple[Path, Path]":
    """The real shape: the spawn is launched in its problem dir, and its
    briefing files live in the attempts dir on the other branch."""
    (tmp_path / "Problems" / "P").mkdir(parents=True)
    attempts = tmp_path / ".attempts" / "pid1"
    attempts.mkdir(parents=True)
    return tmp_path / "Problems" / "P", attempts


def test_a_relative_path_miss_names_where_the_file_is(tmp_path: Path):
    """A spawn works in TWO directories and a relative path resolves
    against one. The Adversary's `inspect(in="CATALOG.md")` failed and
    the hint walked up to the workspace root and listed the repo — true,
    useless, and a round trip. Name the file where it actually is."""
    cwd, attempts = _workspace(tmp_path)
    (attempts / "CATALOG.md").write_text("uc_634 is here\n",
                                         encoding="utf-8")

    out = wq.run_queries([{"grep": "uc_634", "in": "CATALOG.md"}],
                         cwd=cwd, max_chars=400)

    assert "CATALOG.md" in out
    assert str(attempts / "CATALOG.md") in out, out
    assert "use that path" in out


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
        [{"find": str(cwd / "proofs" / "*.lean")}], cwd=cwd, max_chars=400)

    assert "NotImplementedError" not in out, out
    assert "L_a.lean" in out, out


def test_a_genuinely_missing_file_still_says_what_is_there(tmp_path: Path):
    """The name-the-file hint must not swallow the older one: when
    nothing of that name exists anywhere, the agent still gets the
    directory listing that saves it an `ls`."""
    cwd, _ = _workspace(tmp_path)
    (cwd / "real.lean").write_text("x\n", encoding="utf-8")

    out = wq.run_queries([{"grep": "x", "in": "nope.md"}],
                         cwd=cwd, max_chars=400)

    assert "nearest existing directory" in out, out
    assert "real.lean" in out, out
