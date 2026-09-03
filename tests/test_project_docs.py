"""The Project docs root — `Problems/<project>/_docs/` (HID §3.6).

What is pinned here is the fence, not the convenience: every refusal
this module can make is a place where a path could otherwise have left
the root, and the Assistant's whole write surface is one call into
`write(area='agent')`. A hole here is a hole in §1.1's capability
matrix, so each refusal gets its own test and each refusal message has
to name the way out (a refusal an agent cannot act on is a refusal it
routes around — `gate_must_name_a_reachable_action`).
"""
from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

import pytest

from Tooling.state import project_docs as pd
from Tooling.state import projects as _projects


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    (tmp_path / "Problems").mkdir()
    return tmp_path


# ---------------------------------------------------------------- the root

def test_the_root_is_a_name_no_problem_segment_can_take(ws: Path) -> None:
    """§3.6's whole argument for the leading underscore: `_docs` is not
    a legal problem-name segment, so the docs root cannot collide with
    a sibling problem directory."""
    assert pd.root(ws, "Erdos") == ws / "Problems" / "Erdos" / "_docs"
    assert not _projects.NAME_RE.fullmatch(pd.ROOT_DIRNAME)


def test_an_invalid_project_name_never_reaches_the_filesystem(ws: Path) -> None:
    with pytest.raises(ValueError):
        pd.root(ws, "../../etc")


# ------------------------------------------------------------- round trips

def test_write_then_read_round_trip(ws: Path) -> None:
    rel = pd.write(ws, "Erdos", "user/notes.md", "# hello\n")
    assert rel == "user/notes.md"
    assert (ws / "Problems" / "Erdos" / "_docs" / "user"
            / "notes.md").read_text(encoding="utf-8") == "# hello\n"
    assert pd.read(ws, "Erdos", "user/notes.md") == b"# hello\n"


def test_tree_lists_both_areas_with_directories(ws: Path) -> None:
    pd.write(ws, "Erdos", "user/notes.md", "n")
    pd.write(ws, "Erdos", "agent/deep/summary.md", "s", area=pd.AREA_AGENT)
    entries = pd.tree(ws, "Erdos")
    assert [(e["path"], e["kind"]) for e in entries] == [
        ("agent", "dir"), ("agent/deep", "dir"),
        ("agent/deep/summary.md", "file"),
        ("user", "dir"), ("user/notes.md", "file")]
    assert entries[-1]["size"] == 1


def test_tree_of_a_project_with_no_docs_is_empty(ws: Path) -> None:
    assert pd.tree(ws, "Erdos") == []


def test_mkdir_then_delete_an_empty_directory(ws: Path) -> None:
    assert pd.mkdir(ws, "Erdos", "user/chapter") == "user/chapter"
    assert (ws / "Problems" / "Erdos" / "_docs" / "user" / "chapter").is_dir()
    pd.delete(ws, "Erdos", "user/chapter")
    assert not (ws / "Problems" / "Erdos" / "_docs" / "user"
                / "chapter").exists()


def test_reading_something_that_is_not_there_is_a_missing_thing(
    ws: Path,
) -> None:
    """KeyError = 404, ValueError = refused — the `state/projects.py`
    split, so the endpoints upstream need no second vocabulary."""
    with pytest.raises(KeyError):
        pd.read(ws, "Erdos", "user/ghost.md")


# ----------------------------------------------------------- the refusals

def test_the_agent_area_cannot_write_into_the_user_area(ws: Path) -> None:
    """The Assistant's entire write surface is `area='agent'`. If this
    call could land in `user/` the capability matrix (§1.1) would be a
    comment rather than a mechanism."""
    with pytest.raises(ValueError) as e:
        pd.write(ws, "Erdos", "user/notes.md", "x", area=pd.AREA_AGENT)
    assert "agent/notes.md" in str(e.value)
    assert not (ws / "Problems" / "Erdos" / "_docs" / "user").exists()


def test_a_path_that_climbs_out_is_refused(ws: Path) -> None:
    with pytest.raises(ValueError):
        pd.write(ws, "Erdos", "user/../../../escape.md", "x")


def test_an_absolute_path_is_refused(ws: Path) -> None:
    for raw in ("/etc/passwd.md", "C:\\Windows\\note.md"):
        with pytest.raises(ValueError):
            pd.write(ws, "Erdos", raw, "x")


def test_a_path_with_no_area_names_the_way_out(ws: Path) -> None:
    with pytest.raises(ValueError) as e:
        pd.write(ws, "Erdos", "notes.md", "x")
    assert "user/notes.md" in str(e.value)


def test_an_extension_outside_the_whitelist_is_refused(ws: Path) -> None:
    with pytest.raises(ValueError) as e:
        pd.write(ws, "Erdos", "user/run.py", "print(1)")
    assert ".md" in str(e.value)


def _link_dir(link: Path, target: Path) -> None:
    """A directory link, by whichever mechanism this account has.

    Windows refuses `os.symlink` to an unprivileged account (WinError
    1314) but allows a JUNCTION, which `realpath` resolves the same way
    — so the fence stays exercised on the machine it ships from instead
    of skipping there and being tested nowhere."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    if os.name != "nt":  # pragma: no cover — POSIX symlinks just work
        pytest.skip("this account cannot create links")
    import subprocess
    rc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link),
                         str(target)], capture_output=True).returncode
    if rc != 0:  # pragma: no cover
        pytest.skip("this account cannot create links")


def test_a_symlink_out_of_the_root_is_refused(ws: Path) -> None:
    """Normalising the string is not enough — the escape that survives
    normalisation is a link, and §3.6 names it."""
    outside = ws / "outside"
    outside.mkdir()
    (pd.root(ws, "Erdos") / "user").mkdir(parents=True)
    _link_dir(pd.root(ws, "Erdos") / "user" / "away", outside)
    with pytest.raises(ValueError):
        pd.write(ws, "Erdos", "user/away/leak.md", "x")
    assert not (outside / "leak.md").exists()


def test_delete_refuses_a_populated_directory(ws: Path) -> None:
    pd.write(ws, "Erdos", "user/chapter/one.md", "x")
    with pytest.raises(ValueError) as e:
        pd.delete(ws, "Erdos", "user/chapter")
    assert "one.md" in str(e.value) or "empty" in str(e.value)
    assert pd.read(ws, "Erdos", "user/chapter/one.md") == b"x"


# ------------------------------------------------------------------ move

def test_move_renames_a_file_and_leaves_nothing_behind(ws: Path) -> None:
    pd.write(ws, "Erdos", "user/draft.md", "body")
    assert pd.move(ws, "Erdos", "user/draft.md",
                   "user/chapter/final.md") == "user/chapter/final.md"
    assert pd.read(ws, "Erdos", "user/chapter/final.md") == b"body"
    with pytest.raises(KeyError):
        pd.read(ws, "Erdos", "user/draft.md")


def test_move_takes_a_folder_and_everything_under_it(ws: Path) -> None:
    pd.write(ws, "Erdos", "user/old/one.md", "x")
    assert pd.move(ws, "Erdos", "user/old", "user/new") == "user/new"
    assert pd.read(ws, "Erdos", "user/new/one.md") == b"x"
    assert not (pd.root(ws, "Erdos") / "user" / "old").exists()


def test_move_refuses_to_overwrite(ws: Path) -> None:
    pd.write(ws, "Erdos", "user/a.md", "a")
    pd.write(ws, "Erdos", "user/b.md", "b")
    with pytest.raises(ValueError) as e:
        pd.move(ws, "Erdos", "user/a.md", "user/b.md")
    assert "b.md" in str(e.value)
    assert pd.read(ws, "Erdos", "user/b.md") == b"b"
    assert pd.read(ws, "Erdos", "user/a.md") == b"a"


def test_move_refuses_to_cross_into_the_agent_area(ws: Path) -> None:
    """The write fence is the same one `write`/`mkdir`/`delete` carry —
    a rename that lands in `agent/` would merge the two areas §1.2-1
    separates."""
    pd.write(ws, "Erdos", "user/note.md", "x")
    with pytest.raises(ValueError) as e:
        pd.move(ws, "Erdos", "user/note.md", "agent/note.md")
    assert "user/" in str(e.value)
    assert not (pd.root(ws, "Erdos") / "agent").exists()
    with pytest.raises(ValueError):
        pd.move(ws, "Erdos", "agent/x.md", "user/x.md")


def test_move_refuses_an_extension_off_the_whitelist(ws: Path) -> None:
    pd.write(ws, "Erdos", "user/note.md", "x")
    with pytest.raises(ValueError) as e:
        pd.move(ws, "Erdos", "user/note.md", "user/note.exe")
    assert ".md" in str(e.value)
    assert pd.read(ws, "Erdos", "user/note.md") == b"x"


def test_move_refuses_a_folder_into_its_own_descendant(ws: Path) -> None:
    pd.write(ws, "Erdos", "user/chapter/one.md", "x")
    with pytest.raises(ValueError) as e:
        pd.move(ws, "Erdos", "user/chapter", "user/chapter/inner")
    assert "chapter" in str(e.value)
    assert pd.read(ws, "Erdos", "user/chapter/one.md") == b"x"


def test_move_of_a_missing_document_is_a_keyerror(ws: Path) -> None:
    with pytest.raises(KeyError):
        pd.move(ws, "Erdos", "user/ghost.md", "user/other.md")


def test_locate_fences_the_place_as_well_as_the_bytes(ws: Path) -> None:
    """A caller that needs the folder a document sits in (the TeX
    render's search path) must not join the strings itself."""
    assert pd.locate(ws, "Erdos", "user/ch/paper.tex") == (
        pd.root(ws, "Erdos") / "user" / "ch" / "paper.tex")
    with pytest.raises(ValueError):
        pd.locate(ws, "Erdos", "../../escape.tex")


# --------------------------------------------- the notes reach the agents

def _owner_notes(ws: Path, problem: str = "Erdos.p1") -> "list[str]":
    from Tooling.agent import context as _ctx
    from Tooling.state import intent as _intent
    return _ctx._section_owner_notes(
        _intent.ProblemIntent(problem=problem), ws)


def test_owner_notes_section_names_path_size_date_and_title(
        ws: Path) -> None:
    """§1.2/§3.6 put a person's writing under `_docs/user/`, and the
    envelope already lets a worker read it — but nothing ever SAID the
    notes were there, so they were undiscoverable. One line per note:
    the workspace-relative path (what `inspect` is handed), how big it
    is, when it was written, and the title the writer put first — the
    reader decides from that whether to open it."""
    pd.write(ws, "Erdos", "user/split_note.md",
             "# SPLIT: abundance across a cut\n\nbody\n")
    lines = _owner_notes(ws)
    assert lines[0] == "## Owner's notes"
    assert ("The owner left these notes for this Project; read the ones "
            "whose title bears on your work (`inspect` / Read)."
            in lines)
    entry = next(ln for ln in lines if "split_note.md" in ln)
    assert "Problems/Erdos/_docs/user/split_note.md" in entry
    assert "KB" in entry
    assert _dt.datetime.now(_dt.timezone.utc).date().isoformat() in entry
    assert "SPLIT: abundance across a cut" in entry
    assert "#" not in entry.split("KB", 1)[1]  # the heading's # is stripped
    # Never the body — a note is grepped and read on demand, not copied
    # into every wake.
    assert "body" not in "\n".join(lines)


def test_owner_notes_section_is_absent_when_the_owner_wrote_none(
        ws: Path) -> None:
    """No heading for an empty body: a Project with no notes must not
    spend a section telling every wake so."""
    assert _owner_notes(ws) == []
    pd.write(ws, "Erdos", "agent/summary.md", "# agent wrote this\n",
             area=pd.AREA_AGENT)
    pd.write(ws, "Erdos", "user/diagram.png", b"\x89PNG")
    assert _owner_notes(ws) == []


def test_owner_notes_section_excludes_the_papers_shelf(ws: Path) -> None:
    """§3.9 parks fetched papers under `_docs/<area>/papers/<id>/`, and
    they have their own `## Paper` section. Listing `text.md` here would
    put a 200-page extraction in a list of the owner's own writing."""
    pd.write(ws, "Erdos", "user/papers/abc123/text.md", "## p.1\n")
    pd.write(ws, "Erdos", "user/papers/abc123/map.md", "# Map\n")
    assert _owner_notes(ws) == []
    pd.write(ws, "Erdos", "user/note.tex", r"\section{x}" + "\n")
    joined = "\n".join(_owner_notes(ws))
    assert "note.tex" in joined and "papers" not in joined
