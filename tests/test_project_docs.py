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

def _owner_notes(ws: Path, problem: str = "Erdos.p1",
                 conn=None) -> "list[str]":
    from Tooling.agent import context as _ctx
    from Tooling.state import intent as _intent
    return _ctx._section_owner_notes(
        _intent.ProblemIntent(problem=problem), ws, conn)


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
    # 2026-09-04 (theory_wake_design.md §3.2): the section covers BOTH
    # halves of the shelf now, so its heading names the subject rather
    # than one of the two writers.
    assert lines[0] == "## Notes on this problem"
    assert "### The owner wrote these" in lines
    entry = next(ln for ln in lines if "split_note.md" in ln)
    assert "Problems/Erdos/_docs/user/split_note.md" in entry
    assert "KB" in entry
    assert _dt.datetime.now(_dt.timezone.utc).date().isoformat() in entry
    assert "SPLIT: abundance across a cut" in entry
    assert "#" not in entry.split("KB", 1)[1]  # the heading's # is stripped
    # Never the body — a note is grepped and read on demand, not copied
    # into every wake.
    assert "body" not in "\n".join(lines)


def test_owner_notes_section_is_absent_when_nobody_wrote_anything(
        ws: Path) -> None:
    """No heading for an empty body: a Project with no notes must not
    spend a section telling every wake so. A binary is not a note."""
    assert _owner_notes(ws) == []
    pd.write(ws, "Erdos", "user/diagram.png", b"\x89PNG")
    assert _owner_notes(ws) == []


def test_the_roster_lists_what_the_programme_wrote_too(ws: Path) -> None:
    """2026-09-04 (theory_wake_design.md §3.2): `_docs/agent/` is the
    theory layer's shelf, and an accepted theory document is prior work
    of this programme's own. The failure it prevents is not "unread" but
    "re-derived" — both prompts tell their seat to build on it and never
    to present it as new, which is unactionable if nothing says it
    exists."""
    pd.write(ws, "Erdos", "agent/g7_20260904-1200_split.md",
             "# The unit-imbalance erasure\n\nbody\n",
             area=pd.AREA_AGENT)
    lines = _owner_notes(ws)
    assert "### The programme wrote these" in lines
    entry = next(ln for ln in lines if "g7_20260904-1200_split.md" in ln)
    assert "The unit-imbalance erasure" in entry
    assert "body" not in "\n".join(lines)


def test_the_roster_skips_the_reviewer_files_kept_beside_a_document(
        ws: Path) -> None:
    """`preserve` (2026-09-08) copies what a theory REVIEWER wrote into
    `agent/<document-stem>/review_r<n>/` so the document's citations
    still resolve once the round dir is deleted. They are reached
    through that document, never listed as documents of their own —
    each carries no `theory_documents` row, so the roster would have
    shown `review_notes.md` as an accepted programme document with no
    verdict mark at all."""
    pd.write(ws, "Erdos", "agent/g7_20260908-1200_t10.md",
             "# T10 remains open\n\nbody\n", area=pd.AREA_AGENT)
    kept = (pd.root(ws, "Erdos") / "agent" / "g7_20260908-1200_t10"
            / "review_r4")
    kept.mkdir(parents=True)
    (kept / "review_notes.md").write_text(
        "# Reviewer notes\n\nthe theorem it proved past the stop\n",
        encoding="utf-8")
    lines = _owner_notes(ws)
    assert any("g7_20260908-1200_t10.md" in ln for ln in lines), lines
    assert not any("review_notes.md" in ln for ln in lines), lines


def test_an_agent_document_carries_its_group_date_and_verdict(
        ws: Path) -> None:
    """The three facts an agent document's own prose does not have.
    Read off `theory_documents`, not off the file: the row is where the
    review's ruling lives."""
    from Tooling.state import db as _db
    from Tooling.state import groups as _groups
    conn = _db.connect(ws / "t.db")
    _db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
                 " VALUES ('Erdos.p1', ?, 1)", (_db.now(),))
    conn.commit()
    gid = _groups.ensure_top_group(conn, "Erdos.p1")
    name = f"g{gid}_20260904-1200_split.md"
    rel = f"Problems/Erdos/_docs/agent/{name}"
    pd.write(ws, "Erdos", f"agent/{name}",
             "# The unit-imbalance erasure\n", area=pd.AREA_AGENT)
    conn.execute(
        "INSERT INTO theory_documents (problem, group_id, objective,"
        " situation, path, status, rounds, created_at)"
        " VALUES ('Erdos.p1', ?, 'o', 's', ?, 'accepted', 2,"
        " '2026-09-04T12:00:00+00:00')", (gid, rel))
    conn.commit()
    entry = next(ln for ln in _owner_notes(ws, conn=conn) if name in ln)
    assert f"group {gid}" in entry and "2026-09-04" in entry
    assert "review accepted" in entry


def test_a_refused_document_is_listed_under_its_own_sub_list(
        ws: Path) -> None:
    """Owner ruling 2026-09-06: a refused theory document lands too, and
    the roster must not let a reader mistake it for prior work that
    holds. Its own sub-list, the criteria that fired, and the framework's
    one sentence about what a rigour-defective document's results are.

    Citability follows criterion 2 (Rigour), not the status: the
    document refused on 1/3 had its theorems re-derived and may be
    cited; the one refused on 2 carries attempts, and the flag says so
    on the line the reader decides from."""
    import json as _json
    from Tooling.state import db as _db
    from Tooling.state import groups as _groups
    conn = _db.connect(ws / "t.db")
    _db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
                 " VALUES ('Erdos.p1', ?, 1)", (_db.now(),))
    conn.commit()
    gid = _groups.ensure_top_group(conn, "Erdos.p1")

    def _file(name: str, status: str, ruling) -> None:
        pd.write(ws, "Erdos", f"agent/{name}", f"# {name}\n",
                 area=pd.AREA_AGENT)
        conn.execute(
            "INSERT INTO theory_documents (problem, group_id, objective,"
            " situation, path, status, rounds, verdict_json, created_at)"
            " VALUES ('Erdos.p1', ?, 'o', 's', ?, ?, 2, ?,"
            " '2026-09-06T12:00:00+00:00')",
            (gid, f"Problems/Erdos/_docs/agent/{name}", status,
             None if ruling is None else _json.dumps(ruling)))

    def _ruling(**fired) -> dict:
        base = {k: [f"clear: criterion {k} holds"] for k in "1234"}
        base.update({k: [f"fired: {v}"] for k, v in fired.items()})
        return {"criteria": base}

    _file("g1_20260906-1200_kept.md", "accepted", _ruling())
    _file("g1_20260906-1201_citable.md", "rejected",
          _ruling(**{"1": "answers a different request",
                     "3": "the wall is only named"}))
    _file("g1_20260906-1202_attempts.md", "rejected",
          _ruling(**{"2": "Lemma 3 is asserted"}))
    conn.commit()

    lines = _owner_notes(ws, conn=conn)
    assert "### The programme wrote these" in lines
    accepted = next(ln for ln in lines if "kept.md" in ln)
    assert "review accepted" in accepted

    # A sub-list of their own, under the accepted one.
    refused_heading = next(
        i for i, ln in enumerate(lines)
        if ln.startswith("### ") and "refused" in ln.lower())
    assert refused_heading > lines.index("### The programme wrote these")
    tail = "\n".join(lines[refused_heading:])
    assert "kept.md" not in tail

    citable = next(ln for ln in lines if "citable.md" in ln)
    assert "rejected" in citable
    assert "criteria 1, 3" in citable
    assert "rigour" not in citable

    attempts = next(ln for ln in lines if "attempts.md" in ln)
    assert "rejected" in attempts and "criteria 2" in attempts
    assert "rigour defective — see criterion 2" in attempts

    # the framework's own sentence, once, in the sub-list's blurb
    assert "not established" in tail


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


# ------------------------- the shelf is the Project's, not the problem's

def _top_group(conn, problem: str) -> int:
    from Tooling.state import groups as _groups
    return _groups.ensure_top_group(conn, problem)


def _shelf(ws: Path):
    """A Project whose `_docs/agent/` holds documents of three problems
    — the flagship shape (46 Erdos problems, one shelf)."""
    import json as _json
    from Tooling.state import db as _db
    from Tooling.state import groups as _groups
    conn = _db.connect(ws / "t.db")
    _db.init_schema(conn)
    gids: "dict[str, int]" = {}
    for name in ("Erdos.p1", "Erdos.p2", "Erdos.p3", "Erdos.p9"):
        conn.execute("INSERT INTO problems (name, created_at,"
                     " bootstrap_done) VALUES (?, ?, 1)", (name, _db.now()))
        gids[name] = _groups.ensure_top_group(conn, name)
    conn.commit()

    def _doc(problem: str, name: str, status: str = "accepted") -> None:
        pd.write(ws, "Erdos", f"agent/{name}", f"# {name} title\n",
                 area=pd.AREA_AGENT)
        conn.execute(
            "INSERT INTO theory_documents (problem, group_id, objective,"
            " situation, path, status, rounds, verdict_json, created_at)"
            " VALUES (?, ?, 'o', 's', ?, ?, 2, ?,"
            " '2026-09-07T12:00:00+00:00')",
            (problem, gids[problem],
             f"Problems/Erdos/_docs/agent/{name}", status,
             _json.dumps({"criteria": {
                 k: [f"clear: criterion {k} holds"] for k in "1234"}})))

    _doc("Erdos.p1", "g1_20260907-1200_mine.md")
    _doc("Erdos.p2", "g2_20260907-1201_neighbour.md")
    _doc("Erdos.p3", "g3_20260907-1202_stranger.md")
    conn.commit()
    return conn


def test_only_this_problems_documents_are_this_problems_record(
        ws: Path) -> None:
    """Nine reports on 2026-09-07 (Strategist / Adversary / Theorist,
    six problems) said the same thing: `## Notes on this problem` listed
    documents whose abstracts are about a different Erdos problem
    entirely, and each seat had to open one to find that out. The shelf
    is the PROJECT's; `theory_documents.problem` says whose document a
    document is."""
    conn = _shelf(ws)
    lines = _owner_notes(ws, conn=conn)
    text = "\n".join(lines)
    own = text.split(_ctx_other_heading())[0]
    assert "mine.md" in own
    assert "neighbour.md" not in own and "stranger.md" not in own

    others = text.split(_ctx_other_heading())[1]
    assert "Erdos.p2 — " in others and "Erdos.p3 — " in others
    assert "mine.md" not in others
    # named as what it is, on the line the reader decides from
    assert "not this problem's record" in _ctx_other_heading()


def _ctx_other_heading() -> str:
    from Tooling.agent import context as _ctx
    return _ctx.OTHER_PROBLEMS_HEADING


def test_the_neighbours_section_is_its_own_top_level_section(
        ws: Path) -> None:
    """Not a sub-list under `## Notes on this problem`: everything under
    that heading must be about this problem, and a `###` would go on
    being read as one more shelf of the same record."""
    conn = _shelf(ws)
    lines = _owner_notes(ws, conn=conn)
    assert _ctx_other_heading() in lines
    assert lines.index("## Notes on this problem") < lines.index(
        _ctx_other_heading())


def test_a_document_with_no_row_stays_where_it_is(ws: Path) -> None:
    """An owner-placed or reviewer-preserved file has no
    `theory_documents` row, so nothing says it belongs to another
    problem — and nothing may move it out of this problem's list."""
    conn = _shelf(ws)
    pd.write(ws, "Erdos", "agent/unrowed.md", "# no row\n",
             area=pd.AREA_AGENT)
    lines = _owner_notes(ws, conn=conn)
    own = "\n".join(lines).split(_ctx_other_heading())[0]
    assert "unrowed.md" in own


def test_a_neighbours_refused_document_is_counted_not_listed(
        ws: Path) -> None:
    """A refused document is its own problem's record of an approach
    that failed on ITS wall — the refused sub-list's blurb says exactly
    that — so carrying a neighbour's into this problem's roster is the
    same misfiling one layer down. Counted, so the shelf is not
    misrepresented as smaller than it is."""
    import json as _json
    conn = _shelf(ws)
    pd.write(ws, "Erdos", "agent/g2_20260907-1210_refused.md",
             "# refused\n", area=pd.AREA_AGENT)
    conn.execute(
        "INSERT INTO theory_documents (problem, group_id, objective,"
        " situation, path, status, rounds, verdict_json, created_at)"
        " VALUES ('Erdos.p2', ?, 'o', 's',"
        " 'Problems/Erdos/_docs/agent/g2_20260907-1210_refused.md',"
        " 'rejected', 3, ?, '2026-09-07T12:10:00+00:00')",
        (_top_group(conn, "Erdos.p2"),
         _json.dumps({"criteria": {"2": ["fired: Lemma 3 is asserted"]}})))
    conn.commit()
    text = "\n".join(_owner_notes(ws, conn=conn))
    assert "refused.md" not in text
    assert "1 refused document(s) of other problems" in text


def test_the_neighbours_list_is_capped_and_says_how_to_see_the_rest(
        ws: Path) -> None:
    from Tooling.agent import context as _ctx
    conn = _shelf(ws)
    for i in range(_ctx.MAX_OTHER_PROBLEM_DOCS + 4):
        name = f"g9_20260907-13{i:02d}_bulk{i}.md"
        pd.write(ws, "Erdos", f"agent/{name}", f"# bulk {i}\n",
                 area=pd.AREA_AGENT)
        conn.execute(
            "INSERT INTO theory_documents (problem, group_id, objective,"
            " situation, path, status, rounds, created_at)"
            " VALUES ('Erdos.p9', ?, 'o', 's', ?, 'accepted', 1,"
            " '2026-09-07T13:00:00+00:00')",
            (_top_group(conn, "Erdos.p9"),
             f"Problems/Erdos/_docs/agent/{name}"))
    conn.commit()
    text = "\n".join(_owner_notes(ws, conn=conn))
    others = text.split(_ctx_other_heading())[1]
    assert others.count("\n- Erdos.") == _ctx.MAX_OTHER_PROBLEM_DOCS
    assert "not listed" in others
    assert "Problems/Erdos/_docs/agent" in others


def test_no_neighbours_no_section(ws: Path) -> None:
    """A Project of one problem pays nothing for the split."""
    import json as _json
    from Tooling.state import db as _db
    from Tooling.state import groups as _groups
    conn = _db.connect(ws / "t.db")
    _db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
                 " VALUES ('Erdos.p1', ?, 1)", (_db.now(),))
    gid = _groups.ensure_top_group(conn, "Erdos.p1")
    pd.write(ws, "Erdos", "agent/g1_20260907-1200_mine.md", "# mine\n",
             area=pd.AREA_AGENT)
    conn.execute(
        "INSERT INTO theory_documents (problem, group_id, objective,"
        " situation, path, status, rounds, verdict_json, created_at)"
        " VALUES ('Erdos.p1', ?, 'o', 's',"
        " 'Problems/Erdos/_docs/agent/g1_20260907-1200_mine.md',"
        " 'accepted', 1, ?, '2026-09-07T12:00:00+00:00')",
        (gid, _json.dumps({"criteria": {}})))
    conn.commit()
    lines = _owner_notes(ws, conn=conn)
    assert _ctx_other_heading() not in "\n".join(lines)
