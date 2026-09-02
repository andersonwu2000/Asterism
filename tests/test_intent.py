"""state.intent — the DB-resident problem intent (v40, Manifest.md
retired): charter = top group's `groups.charter`, word =
`problems.user_word`, settings = `problem_settings`; problem.json is
the durable seed the intent writers mirror. Successor of
test_manifest.py — the parser those tests pinned is deleted; the
invariants that survived (Defs.lean open propagation, effective_axioms
semantics, spawn write-deny) are ported here."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db as _db
from Tooling.state import groups as _groups
from Tooling.state import intent
from Tooling.state import settings as _settings


def _seed_problem(conn: sqlite3.Connection, name: str = "P",
                  charter: str = "Prove the thing.") -> None:
    conn.execute(
        "INSERT INTO problems (name, created_at) VALUES (?, ?)",
        (name, _db.now()))
    _groups.ensure_top_group(conn, name, charter=charter)
    conn.commit()


# ---------------------------------------------------------------------
# read / write / history
# ---------------------------------------------------------------------


def test_read_assembles_charter_word_settings(
        conn: sqlite3.Connection) -> None:
    _seed_problem(conn, "P", charter="Settle Frankl.")
    _settings.write(conn, "P", "library", True)
    intent.set_word(conn, "P", "Fold the tree.")
    pi = intent.read(conn, "P")
    assert pi is not None
    assert pi.charter == "Settle Frankl."
    assert pi.word == "Fold the tree."
    assert pi.library is True
    assert pi.signoff is True          # absent key → framework default


def test_read_unknown_problem_is_none(conn: sqlite3.Connection) -> None:
    assert intent.read(conn, "ghost") is None


def test_set_charter_updates_top_group_and_records_history(
        conn: sqlite3.Connection) -> None:
    _seed_problem(conn, "P", charter="old goal")
    intent.set_charter(conn, "P", "new goal")
    top = _groups.top_group(conn, "P")
    assert str(top["charter"]) == "new goal"
    rows = conn.execute(
        "SELECT body, source FROM user_file_history"
        " WHERE problem = 'P' AND file = 'charter' ORDER BY id"
    ).fetchall()
    assert rows and rows[-1]["body"] == "new goal"
    assert rows[-1]["source"] == "repin"   # sanctioned change ack


def test_set_charter_refuses_empty(conn: sqlite3.Connection) -> None:
    _seed_problem(conn, "P")
    with pytest.raises(ValueError):
        intent.set_charter(conn, "P", "   ")


def test_set_word_empty_is_legal_withdrawal(
        conn: sqlite3.Connection) -> None:
    _seed_problem(conn, "P")
    intent.set_word(conn, "P", "do X")
    intent.set_word(conn, "P", "")
    assert intent.read(conn, "P").word == ""
    n = conn.execute(
        "SELECT COUNT(*) FROM user_file_history"
        " WHERE problem = 'P' AND file = 'word'").fetchone()[0]
    assert n == 2


def test_word_is_not_machine_amendable() -> None:
    """The user's word has no RequestUserAmend path — both the
    strategist gate enum and the amend resolver whitelist must exclude
    it, and both must accept 'charter' (source pins on the two SoTs)."""
    from Tooling.pipeline.strategist import USER_AMEND_FILES
    from Tooling.state.amend import _ALLOWED_FILES
    assert "word" not in USER_AMEND_FILES
    assert "word" not in _ALLOWED_FILES
    assert "charter" in USER_AMEND_FILES
    assert "charter" in _ALLOWED_FILES
    assert "Manifest.md" not in USER_AMEND_FILES
    assert "Manifest.md" not in _ALLOWED_FILES


def test_user_intent_files_are_the_two_lean_files() -> None:
    assert intent.USER_INTENT_FILES == ("Root.lean", "Defs.lean")
    assert intent.DB_INTENT_KEYS == ("charter", "word")


# ---------------------------------------------------------------------
# The durable seed (problem.json)
# ---------------------------------------------------------------------


def _file_workspace(tmp_path: Path, name: str = "P",
                    charter: str = "Goal.") -> sqlite3.Connection:
    """A real on-disk DB so _workspace_of resolves (the seed mirror
    skips on :memory:)."""
    (tmp_path / "Problems" / name).mkdir(parents=True)
    conn = _db.connect(tmp_path / "asterism.db")
    _db.init_schema(conn)
    _seed_problem(conn, name, charter=charter)
    return conn


def test_writers_mirror_the_seed(tmp_path: Path) -> None:
    conn = _file_workspace(tmp_path, "P", charter="Goal v1")
    intent.set_word(conn, "P", "the word")
    seed = json.loads(
        (tmp_path / "Problems" / "P" / "problem.json").read_text(
            encoding="utf-8"))
    assert seed["charter"] == "Goal v1"
    assert seed["word"] == "the word"
    intent.set_charter(conn, "P", "Goal v2")
    seed = json.loads(
        (tmp_path / "Problems" / "P" / "problem.json").read_text(
            encoding="utf-8"))
    assert seed["charter"] == "Goal v2"
    conn.close()


def test_settings_write_mirrors_the_seed(tmp_path: Path) -> None:
    conn = _file_workspace(tmp_path, "P")
    _settings.write(conn, "P", "library", True)
    seed = json.loads(
        (tmp_path / "Problems" / "P" / "problem.json").read_text(
            encoding="utf-8"))
    assert seed["settings"]["library"] is True
    conn.close()


def test_read_seed_requires_charter(tmp_path: Path) -> None:
    p = tmp_path / "problem.json"
    p.write_text('{"problem": "P"}', encoding="utf-8")
    with pytest.raises(ValueError):
        intent.read_seed(p)
    assert intent.read_seed(tmp_path / "missing.json") is None


def test_memory_db_skips_seed_mirror(conn: sqlite3.Connection) -> None:
    # :memory: fixture — the write must succeed without a workspace.
    _seed_problem(conn, "P")
    intent.set_word(conn, "P", "no crash")
    assert intent.read(conn, "P").word == "no crash"


# ---------------------------------------------------------------------
# IntentCache — DB-backed dict view, live on next access
# ---------------------------------------------------------------------


def test_intent_cache_serves_fresh_db_state(tmp_path: Path) -> None:
    conn = _file_workspace(tmp_path, "P", charter="Goal v1")
    cache = intent.IntentCache(tmp_path)
    assert cache.load("P") is not None
    assert cache["P"].charter == "Goal v1"
    intent.set_charter(conn, "P", "Goal v2")   # UI/CLI edit mid-run
    assert cache["P"].charter == "Goal v2"     # no restart, no mtime
    conn.close()


def test_intent_cache_dict_compat(tmp_path: Path) -> None:
    conn = _file_workspace(tmp_path, "P")
    cache = intent.IntentCache(tmp_path)
    cache.load("P")
    assert "P" in cache and len(cache) == 1
    assert list(cache.keys()) == ["P"]
    assert [p for p, _ in cache.items()] == ["P"]
    with pytest.raises(KeyError):
        cache["never_loaded"]
    conn.close()


def test_intent_cache_load_missing_problem_returns_none(
        tmp_path: Path) -> None:
    conn = _file_workspace(tmp_path, "P")
    cache = intent.IntentCache(tmp_path)
    assert cache.load("ghost") is None
    assert "ghost" not in cache
    conn.close()


def test_intent_cache_sweeps_user_files_into_history(
        tmp_path: Path) -> None:
    conn = _file_workspace(tmp_path, "P")
    root = tmp_path / "Problems" / "P" / "Root.lean"
    root.write_text("theorem main : True := by sorry\n", encoding="utf-8")
    cache = intent.IntentCache(tmp_path)
    cache.load("P")
    row = conn.execute(
        "SELECT sha FROM user_file_history"
        " WHERE problem = 'P' AND file = 'Root.lean'").fetchone()
    assert row is not None
    conn.close()


# ---------------------------------------------------------------------
# effective_axioms — semantics unchanged from the manifest era
# ---------------------------------------------------------------------


def test_effective_axioms_set_field_passes_through() -> None:
    pi = intent.ProblemIntent(problem="p",
                              axioms_whitelist=["propext", "Custom.ax"])
    assert intent.effective_axioms(pi) == ["propext", "Custom.ax"]


def test_effective_axioms_strips_sorryAx() -> None:
    """Whitelist-edition sorryAx tripwire (self-audit 2026-07-12 §3-1c):
    no configuration may authorize an unproven proof — sorryAx is
    stripped at THE derivation chokepoint, and a sorryAx-only whitelist
    degrades to the framework defaults, never to an empty gate."""
    intent._default_axioms_warned.clear()
    pi = intent.ProblemIntent(problem="p_sry",
                              axioms_whitelist=["propext", "sorryAx"])
    assert intent.effective_axioms(pi) == ["propext"]
    pi2 = intent.ProblemIntent(problem="p_sry2",
                               axioms_whitelist=["sorryAx"])
    wl2 = intent.effective_axioms(pi2)
    assert wl2 == list(intent.FRAMEWORK_DEFAULT_AXIOMS)
    assert "sorryAx" not in wl2


def test_effective_axioms_empty_falls_back_to_framework_default(
        capsys) -> None:
    """Absent setting NEVER weakens a gate: framework default, warned
    once per problem (not once per gate call)."""
    intent._default_axioms_warned.clear()
    pi = intent.ProblemIntent(problem="p_eff")
    wl = intent.effective_axioms(pi)
    assert wl == list(intent.FRAMEWORK_DEFAULT_AXIOMS)
    assert "sorryAx" not in wl
    out = capsys.readouterr().out
    assert "framework default" in out
    intent.effective_axioms(pi)                     # second call: silent
    assert "framework default" not in capsys.readouterr().out


def test_effective_axioms_verify_reexport_is_same_object() -> None:
    from Tooling.quality import verify
    assert verify.FRAMEWORK_DEFAULT_AXIOMS is intent.FRAMEWORK_DEFAULT_AXIOMS


# ---------------------------------------------------------------------
# Defs.lean `open` clause propagation (ported verbatim)
# ---------------------------------------------------------------------


def _make_problem_dir(tmp_path: Path, name: str,
                      opens: "list[str]") -> None:
    pdir = tmp_path / "Problems" / name
    pdir.mkdir(parents=True)
    lines = ["import Mathlib", ""]
    lines += [f"open {o}" for o in opens]
    lines += ["", "theorem helper : True := trivial", ""]
    (pdir / "Defs.lean").write_text("\n".join(lines), encoding="utf-8")


def test_defs_opens_returns_top_level_opens(tmp_path: Path) -> None:
    _make_problem_dir(tmp_path, "wilson",
                      ["BigOperators Real Nat", "Topology"])
    assert intent.defs_opens(tmp_path, "wilson") == [
        "BigOperators Real Nat", "Topology",
    ]


def test_defs_opens_returns_empty_when_no_defs(tmp_path: Path) -> None:
    (tmp_path / "Problems" / "wilson").mkdir(parents=True)
    assert intent.defs_opens(tmp_path, "wilson") == []


def test_defs_opens_skips_scope_limited_opens(tmp_path: Path) -> None:
    pdir = tmp_path / "Problems" / "wilson"
    pdir.mkdir(parents=True)
    (pdir / "Defs.lean").write_text(
        "import Mathlib\n\n"
        "open Real\n"           # top-level → propagate
        "open Topology in\n"    # scope-limited → DO NOT propagate
        "theorem helper : True := trivial\n",
        encoding="utf-8",
    )
    assert intent.defs_opens(tmp_path, "wilson") == ["Real"]


def test_inject_defs_opens_adds_missing_opens(tmp_path: Path) -> None:
    _make_problem_dir(tmp_path, "wilson",
                      ["BigOperators Real Nat Topology Rat"])
    content = (
        "import Mathlib\n"
        "import Problems.wilson.Defs\n\n"
        "namespace Problems.wilson\n\n"
        "theorem foo : True := trivial\n\n"
        "end Problems.wilson\n"
    )
    out = intent.inject_defs_opens(content, problem="wilson",
                                   workspace=tmp_path)
    assert "open BigOperators Real Nat Topology Rat" in out
    assert "import Problems.wilson.Defs" in out
    # Open block should sit between imports and namespace.
    idx_import = out.index("import Problems.wilson.Defs")
    idx_open = out.index("open BigOperators")
    idx_ns = out.index("namespace Problems.wilson")
    assert idx_import < idx_open < idx_ns


def test_inject_defs_opens_idempotent(tmp_path: Path) -> None:
    _make_problem_dir(tmp_path, "wilson", ["Real"])
    content = (
        "import Mathlib\n\n"
        "open Real\n\n"
        "namespace Problems.wilson\n\n"
        "theorem foo : True := trivial\n"
    )
    out = intent.inject_defs_opens(content, problem="wilson",
                                   workspace=tmp_path)
    # No new open should be inserted; content unchanged.
    assert out == content
    assert out.count("open Real") == 1


def test_inject_defs_opens_no_defs_returns_unchanged(
    tmp_path: Path,
) -> None:
    (tmp_path / "Problems" / "wilson").mkdir(parents=True)
    content = "import Mathlib\n\nnamespace Problems.wilson\n\nend\n"
    assert intent.inject_defs_opens(content, problem="wilson",
                                    workspace=tmp_path) == content


def test_inject_defs_opens_preserves_existing_subset(
    tmp_path: Path,
) -> None:
    _make_problem_dir(tmp_path, "wilson",
                      ["BigOperators", "Real Nat Topology"])
    content = (
        "import Mathlib\n\n"
        "open BigOperators\n\n"  # already has this one
        "namespace Problems.wilson\n\n"
        "theorem foo : True := trivial\n"
    )
    out = intent.inject_defs_opens(content, problem="wilson",
                                   workspace=tmp_path)
    # `BigOperators` already present → no duplicate; the rest added.
    assert out.count("open BigOperators") == 1
    assert "open Real Nat Topology" in out


# ---------------------------------------------------------------------
# Spawn deny pins (ported: Manifest.md's slot became problem.json)
# ---------------------------------------------------------------------


def test_spawn_cmd_denies_user_file_writes() -> None:
    """Self-audit 2026-07-12 §3-1a: every spawn carries the
    --disallowedTools deny for problem.json / Defs.lean / Root.lean
    (Write + Edit). Source pin — the flag lives in the one cmd builder
    all agent kinds share."""
    src = (Path(__file__).resolve().parents[1]
           / "Tooling" / "llm" / "claude_cli.py").read_text(
               encoding="utf-8")
    assert '"--disallowedTools"' in src
    for f in ("problem.json", "Defs.lean", "Root.lean"):
        assert f'"Write(**/{f})"' in src, f
        assert f'"Edit(**/{f})"' in src, f


def test_spawn_cmd_denies_writes_to_the_rendered_files() -> None:
    """The rendered files are DB projections, not documents: PROGRAMME.md
    from `programme_revisions` (research_mode_design.md §2), REPORT.md
    from `problems.ingest_report` (HID §3.4). A spawn that edits one is
    editing a page the next render silently discards — and, worse, one a
    human reads as the record."""
    src = (Path(__file__).resolve().parents[1]
           / "Tooling" / "llm" / "claude_cli.py").read_text(
               encoding="utf-8")
    for f in ("PROGRAMME.md", "REPORT.md"):
        assert f'"Write(**/{f})"' in src, f
        assert f'"Edit(**/{f})"' in src, f


def test_spawn_isolates_operator_memory() -> None:
    """2026-07-13: Claude Code auto-memory is keyed by git repo root,
    so spawns cwd'd in Problems/<p>/ shared the OPERATOR's memory dir
    (bidirectional: solution leaks in, context injection out). Source
    pin for both layers — the env kill switch and the ~/.claude
    projects-subtree deny rules."""
    src = (Path(__file__).resolve().parents[1]
           / "Tooling" / "llm" / "claude_cli.py").read_text(
               encoding="utf-8")
    # env layer present at the claude spawn call site
    assert src.count('["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"') == 1
    # deny-rule layer wired into the spawn cmd
    assert "*_operator_state_deny_rules()," in src
    from Tooling.llm.claude_cli import _operator_state_deny_rules
    rules = _operator_state_deny_rules()
    assert len(rules) == 3
    for rule, kind in zip(rules, ("Read", "Write", "Edit")):
        assert rule.startswith(f"{kind}(//")
        assert rule.endswith("/.claude/projects/**)")


# ---------------------------------------------------------------------
# The erasure itself
# ---------------------------------------------------------------------


def test_state_manifest_module_is_gone() -> None:
    """v40: the Manifest parser is deleted, not deprecated — an import
    resurrection is the drift this pin exists to catch."""
    with pytest.raises(ModuleNotFoundError):
        import Tooling.state.manifest  # noqa: F401


def test_prompts_carry_no_manifest_noun() -> None:
    """The prompts say "charter" / "the user's word" at every depth;
    the word "Manifest" reappearing means the old two-referent split
    (and the silenced-user-channel bug it caused) is growing back."""
    prompts = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"
    offenders = [p for p in prompts.rglob("*.md")
                 if "Manifest" in p.read_text(encoding="utf-8")]
    assert offenders == [], offenders


# ---------------------------------------------------------------------
# state.projects — Project as a first-class row
# (human_interface_design.md §3.1)
# ---------------------------------------------------------------------


def test_create_project_rejects_a_name_no_problem_could_carry(
        conn: sqlite3.Connection) -> None:
    """A Project name is ONE segment of a problem name, so it answers to
    the same character rule the problem-name gate applies per segment —
    dots included: a dotted Project could never be a problem's prefix."""
    from Tooling.state import projects
    projects.create_project(conn, "Erdos", description="the shelf")
    for bad in ("", "  ", "1starts_with_digit", "has space", "Erdos.p1",
                "semi;colon", "x" * 121):
        with pytest.raises(ValueError):
            projects.create_project(conn, bad)
    assert [p["name"] for p in projects.list_projects(conn)] == ["Erdos"]


def test_create_project_is_not_a_silent_upsert(
        conn: sqlite3.Connection) -> None:
    """Creating over a live Project would erase its description without
    saying so — the second call is a conflict, not a write."""
    from Tooling.state import projects
    projects.create_project(conn, "Erdos", description="the shelf")
    with pytest.raises(ValueError):
        projects.create_project(conn, "Erdos", description="clobbered")
    assert projects.list_projects(conn)[0]["description"] == "the shelf"


def test_rename_project_carries_its_problems(
        conn: sqlite3.Connection) -> None:
    """§3.1: rename is a TABLE operation — the FK follows in the same
    transaction, and neither the problem name nor its directory moves."""
    from Tooling.state import projects
    projects.create_project(conn, "Erdos")
    _seed_problem(conn, "Erdos.p1")
    conn.execute("UPDATE problems SET project = 'Erdos'")
    projects.rename_project(conn, "Erdos", "ErdosProblems")
    assert projects.project_of(conn, "Erdos.p1") == "ErdosProblems"
    assert [p["name"] for p in projects.list_projects(conn)] \
        == ["ErdosProblems"]
    assert conn.execute("SELECT name FROM problems").fetchone()[0] \
        == "Erdos.p1"
    assert list(conn.execute("PRAGMA foreign_key_check")) == []


def test_delete_project_refuses_while_a_problem_names_it(
        conn: sqlite3.Connection) -> None:
    """An empty Project is legal; a populated one is not deletable —
    otherwise the delete either strands a problem or silently takes it."""
    from Tooling.state import projects
    projects.create_project(conn, "Erdos")
    _seed_problem(conn, "Erdos.p1")
    conn.execute("UPDATE problems SET project = 'Erdos'")
    with pytest.raises(ValueError):
        projects.delete_project(conn, "Erdos")
    conn.execute("UPDATE problems SET project = NULL")
    projects.delete_project(conn, "Erdos")
    assert projects.list_projects(conn) == []


def test_set_description_is_the_only_way_the_blurb_changes(
        conn: sqlite3.Connection) -> None:
    from Tooling.state import projects
    projects.create_project(conn, "Erdos")
    projects.set_description(conn, "Erdos", "the open-problems shelf")
    assert projects.list_projects(conn)[0]["description"] \
        == "the open-problems shelf"
    # An unknown name is a MISSING resource, not a bad request — the two
    # exception types are what let the write endpoints answer 404 vs 409
    # without a check-then-act race.
    with pytest.raises(KeyError):
        projects.set_description(conn, "ghost", "nobody")


def test_init_problem_files_a_new_problem_under_its_prefix(
        tmp_path: Path) -> None:
    """Registration MUST set `problems.project` (§3.1: the backfill left
    no row project-less, and a new registration must not reopen the hole)
    — minting the Project row when the prefix names none yet."""
    from Tooling.core.cli import init_problem
    from Tooling.state import projects
    pdir = tmp_path / "Problems" / "Erdos" / "p1"
    pdir.mkdir(parents=True)
    (pdir / "problem.json").write_text(
        json.dumps({"problem": "Erdos.p1", "charter": "Settle it."}),
        encoding="utf-8")
    rc, msg = init_problem(tmp_path, "Erdos.p1", force=True)
    assert rc == 0, msg
    conn = _db.connect(tmp_path / "asterism.db")
    try:
        assert projects.project_of(conn, "Erdos.p1") == "Erdos"
        assert [p["name"] for p in projects.list_projects(conn)] == ["Erdos"]
    finally:
        conn.close()
