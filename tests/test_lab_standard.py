"""`asterism lab run standard …` — the standard test sets.

The sets themselves are the owner's (`<root>/sets/`, in the private
repo); what lives here is the machinery that reads them, runs them and
SCORES them. Four things are worth a test and nothing else is:

  * the table parses, and a mistyped key is a refusal — a standard set
    that silently ran the wrong kind would report a green scorecard for
    an experiment nobody performed.
  * the base workspace's seeded problems come up the way `asterism init`
    brings a problem up (frozen root, top group), because every trap is
    judged against that problem's charter.
  * a trap is judged on the FILES it names, in the workspace's own
    scene, through the same projection a live wake builds.
  * the score is derived from the record and nothing else, and a
    `must_not_fire` criterion that fired is a FAILURE — a scorer that
    only checked the verdict would call a rubric that rebuts everything
    a passing rubric.

Fast by construction: no spawn, no daemon, no Lean. The driver is a
callable the runner takes, and the judge's `review` is a callable the
driver takes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from Tooling import lab
from Tooling.lab import LabError
from Tooling.lab import build as build_mod
from Tooling.lab import driver as driver_mod
from Tooling.lab import gauntlet as gauntlet_mod
from Tooling.lab import standard as std
from Tooling.state import db, groups as groups_mod

ROOT_STMT = "theorem main : ∀ n : ℕ, 1 ≤ n → n ≠ 0 := by sorry\n"


# ---------------------------------------------------------------------
# a sets/ tree, written the way the owner's is
# ---------------------------------------------------------------------

def _sets(root: Path, *, body: str = "", seed: bool = True) -> Path:
    """`<root>/sets/` with one seeded problem and one trap."""
    sets = root / "sets"
    if seed:
        pdir = sets / "base" / "Problems" / "Lab" / "tiny"
        pdir.mkdir(parents=True)
        (pdir / "problem.json").write_text(json.dumps(
            {"problem": "Lab.tiny", "charter": "# Lab.tiny\n\nProve it.\n"}),
            encoding="utf-8")
        (pdir / "Root.lean").write_text(
            "import Mathlib\n\nnamespace Problems.Lab.tiny\n\n" + ROOT_STMT
            + "\nend Problems.Lab.tiny\n", encoding="utf-8")
    t = sets / "traps" / "cheap"
    t.mkdir(parents=True)
    (t / "proposal.md").write_text("# The cheap route\n\nNOW: a table.\n",
                                   encoding="utf-8")
    (t / "decisions.json").write_text(json.dumps(
        [{"kind": "Inject", "proof": "Theorem. decide it.\nProof. decide."}]),
        encoding="utf-8")
    (t / "expected.json").write_text(json.dumps(
        {"verdict": "rebut", "must_fire": ["1"], "must_not_fire": ["2"]}),
        encoding="utf-8")
    s = sets / "smoke" / "probe"
    s.mkdir(parents=True)
    (s / "expected.json").write_text(json.dumps(
        {"outcome": "success", "proved_at_least": 1}), encoding="utf-8")
    (sets / "standard.yaml").write_text(body or _YAML, encoding="utf-8")
    return sets


_YAML = """\
base:
  problems: [base/Problems/Lab/tiny]
  reuse_workspace_problems: [Test.provider_probe]

sets:
  traps:
    kind: judge_round
    problem: Lab.tiny
    group: root
    trigger: inject_batch_done
    items:
      cheap: {proposal: traps/cheap/proposal.md,
              decisions: traps/cheap/decisions.json,
              expected: traps/cheap/expected.json}

  smoke:
    items:
      provider_probe: {kind: daemon, scope: Test.provider_probe, once: true,
                       stop: {proved: 1, wall_sec: 60},
                       expected: smoke/probe/expected.json}
"""


# ---------------------------------------------------------------------
# the table
# ---------------------------------------------------------------------

def test_standard_yaml_names_every_items_kind_inputs_and_expectation(tmp_path):
    """One table, read once. A set's `kind:` / `problem:` / `group:` are
    the default its items inherit — spelling them per item is how five
    traps come to be judged against four charters."""
    _sets(tmp_path)
    sets = std.load(tmp_path)
    assert [i.name for i in sets.items] == ["traps/cheap",
                                            "smoke/provider_probe"]
    trap = sets.items[0]
    assert trap.kind == "judge_round" and trap.problem == "Lab.tiny"
    assert trap.options["group"] == "root"
    assert trap.options["trigger"] == "inject_batch_done"
    # Paths are resolved against the standard.yaml, like every lab input.
    assert Path(trap.options["proposal"]).is_file()
    assert Path(trap.options["decisions"]).is_file()
    assert trap.expected["must_fire"] == ["1"]
    probe = sets.items[1]
    assert probe.kind == "daemon" and probe.problem == "Test.provider_probe"
    assert probe.options["stop"] == {"proved": 1, "wall_sec": 60}
    assert probe.needs_slice, "it names a problem the LIVE workspace holds"
    assert not trap.needs_slice, "it is seeded into the base"
    assert [p.name for p in sets.base_problems] == ["tiny"]


@pytest.mark.parametrize("body,where", [
    ("basis: {}\nsets: {}\n", "basis"),
    ("sets:\n  t:\n    kinds: judge_round\n    items: {a: {}}\n", "kinds"),
    ("sets:\n  t:\n    kind: judge_round\n    problem: p\n    group: 1\n"
     "    items:\n      a: {proposal: traps/cheap/proposal.md, rowz: [1],\n"
     "          expected: traps/cheap/expected.json}\n", "rowz"),
])
def test_standard_yaml_refuses_a_mistyped_key(tmp_path, body, where):
    """The failure a hand-edited table is exposed to is not a crash: a
    mistyped key runs the item against the setting it meant to change
    and looks like it worked."""
    _sets(tmp_path, body=body, seed=False)
    with pytest.raises(LabError) as exc:
        std.load(tmp_path)
    assert where in str(exc.value)


def test_a_judge_item_names_a_proposal_or_historical_rows_but_not_both(
        tmp_path):
    _sets(tmp_path, body=(
        "sets:\n  t:\n    kind: judge_round\n    problem: p\n    group: 1\n"
        "    items:\n      a: {expected: traps/cheap/expected.json}\n"),
        seed=False)
    with pytest.raises(LabError, match="proposal"):
        std.load(tmp_path)


def test_an_item_with_no_expectation_is_not_a_standard_item(tmp_path):
    """"An item with no expectation is not a standard item" — one scored
    against nothing turns the scorecard into a list of runs that
    happened."""
    _sets(tmp_path, body=(
        "sets:\n  t:\n    kind: judge_round\n    problem: p\n    group: 1\n"
        "    items:\n      a: {proposal: traps/cheap/proposal.md}\n"),
        seed=False)
    with pytest.raises(LabError, match="expected"):
        std.load(tmp_path)


# ---------------------------------------------------------------------
# the base workspace's seeded problems
# ---------------------------------------------------------------------

def test_a_seeded_base_problem_comes_up_frozen_with_a_top_group(tmp_path):
    """`lab build` used to make a skeleton with no problems in it, and
    every arm's scene arrived in a slice. A standard set's own problems
    have no slice — they are seeded — so they must be brought up through
    the SAME chokepoint `asterism init` uses: root minted `frozen`, top
    group created from the charter, TREE/BRIEF rendered."""
    _sets(tmp_path)
    base = tmp_path / "base"
    (base / "Problems").mkdir(parents=True)
    seeded = build_mod.seed_base_problems(tmp_path, base)
    assert seeded == ["Lab.tiny"]
    assert (base / "Problems" / "Lab" / "tiny" / "Root.lean").is_file()
    conn = db.connect(base / "asterism.db")
    try:
        row = conn.execute(
            "SELECT status, origin FROM goals WHERE problem = 'Lab.tiny'"
            " AND slug = 'main'").fetchone()
        assert row is not None and row["status"] == "frozen"
        assert row["origin"] == "root"
        top = groups_mod.top_group(conn, "Lab.tiny")
        assert top is not None and "Prove it." in str(top["charter"])
    finally:
        conn.close()
    assert (base / "Problems" / "Lab" / "tiny" / "TREE.md").is_file()
    assert (base / "Problems" / "Lab" / "tiny" / "BRIEF.md").is_file()
    # Idempotent: a second build must not mint a second root.
    assert build_mod.seed_base_problems(tmp_path, base) == ["Lab.tiny"]


# ---------------------------------------------------------------------
# judge_round from files
# ---------------------------------------------------------------------

def _workspace_with_lab_problem(tmp_path) -> Path:
    ws = tmp_path / "ws"
    (ws / "Problems").mkdir(parents=True)
    _sets(tmp_path)
    build_mod.seed_base_problems(tmp_path, ws)
    return ws


def _judge_spec(ws: Path, out: Path, trap) -> dict:
    return {"problem": "Lab.tiny", "options": dict(trap.options),
            "workspace": str(ws), "out": str(out)}


def test_a_judge_item_is_judged_on_the_files_it_names(tmp_path):
    """A trap has no historical revision at all: the proposal and the
    decisions are FILES, and the scene they are judged in is the
    workspace's own current record. `group: root` is the problem's top
    group — the trap set names one charter, not one integer that changed
    the last time the base was rebuilt."""
    ws = _workspace_with_lab_problem(tmp_path)
    trap = std.load(tmp_path).items[0]
    seen: dict = {}

    def _review(**kw):
        seen.update(kw)
        return ({"verdict": "rebut", "criteria": {"1": ["fired: a table"]}},
                "", 0)

    out = tmp_path / "out"
    out.mkdir()
    res = driver_mod.run_judge_round(_judge_spec(ws, out, trap), ws, out,
                                     review=_review)
    assert res["outcome"] == "success"
    assert seen["proposal_body"] == Path(
        trap.options["proposal"]).read_text(encoding="utf-8")
    assert [d.kind for d in seen["decisions"]] == ["Inject"]
    conn = db.connect(ws / "asterism.db")
    try:
        top = groups_mod.top_group(conn, "Lab.tiny")
    finally:
        conn.close()
    assert seen["group_id"] == int(top["id"]), "`group: root` is the top group"
    assert res["rounds"][0]["verdict"]["verdict"] == "rebut"


def test_the_projection_a_judge_item_gets_is_the_live_wakes_projection(
        tmp_path):
    """Not a re-implementation of it. `adversary.build_projection` is
    what a real round calls, so the trap's judge reads the same
    companions — charter.md from the Lab problem's own group, PROGRAMME/
    TREE/CATALOG rendered fresh — with the trap's proposal and decisions
    where the wake's would be."""
    from Tooling.pipeline import adversary

    ws = _workspace_with_lab_problem(tmp_path)
    trap = std.load(tmp_path).items[0]
    proj: "list[Path]" = []

    def _review(**kw):
        proj.append(adversary.build_projection(round_no=1, **{
            k: v for k, v in kw.items()
            if k in ("attempts_dir", "problem_dir", "conn", "problem",
                     "proposal_body", "decisions", "dialogue", "proof_warn",
                     "group_id")}))
        return ({"verdict": "pass", "criteria": {}}, "", 0)

    out = tmp_path / "out"
    out.mkdir()
    driver_mod.run_judge_round(_judge_spec(ws, out, trap), ws, out,
                               review=_review)
    p = proj[0]
    assert "NOW: a table." in (p / "proposal.md").read_text(encoding="utf-8")
    assert "decide it." in (p / "decisions.md").read_text(encoding="utf-8")
    assert "Prove it." in (p / "charter.md").read_text(encoding="utf-8")
    for name in ("PROGRAMME.md", "TREE.md"):
        assert (p / name).is_file(), f"{name} is a live-wake companion"
    # …and the conditional ones are conditional here too, which is the
    # point: CATALOG.md is written only for a problem with proved or
    # alive goals, and a freshly seeded Lab problem has a frozen root
    # and nothing else. The projection is the live one, not a copy of it
    # that always writes four files.
    assert not (p / "CATALOG.md").exists()


# ---------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------

def _judge_record(verdict: str, criteria: dict) -> dict:
    return {"kind": "judge_round", "outcome": "success", "wall_sec": 12.0,
            "driver_result": {"rounds": [{"verdict": {
                "verdict": verdict, "criteria": criteria}}]}}


def test_a_trap_is_scored_on_the_verdict_and_the_criteria_that_fired():
    exp = {"verdict": "rebut", "must_fire": ["1"], "must_not_fire": ["2"]}
    good = std.score("judge_round", exp, _judge_record(
        "rebut", {"1": ["fired: a table"], "2": ["clear: argued"]}))
    assert good["ok"] and good["checks"]["verdict"]["ok"]
    assert good["checks"]["must_fire"]["fired"] == ["1"]


def test_a_trap_caught_for_the_wrong_reason_is_not_a_pass():
    """The control group is what keeps the traps meaningful: a rubric
    that fires everything rebuts every trap and scores five green. So a
    `must_not_fire` criterion that fired FAILS the item even when the
    verdict is the expected one."""
    exp = {"verdict": "rebut", "must_fire": ["1"], "must_not_fire": ["2"]}
    got = std.score("judge_round", exp, _judge_record(
        "rebut", {"1": ["fired: a table"], "2": ["fired: also this"]}))
    assert not got["ok"]
    assert got["checks"]["must_not_fire"]["fired"] == ["2"]


def test_a_trap_the_judge_let_through_is_not_a_pass():
    exp = {"verdict": "rebut", "must_fire": ["1"], "must_not_fire": []}
    got = std.score("judge_round", exp, _judge_record(
        "pass", {"1": ["clear: fine"]}))
    assert not got["ok"]
    assert got["checks"]["verdict"]["got"] == "pass"
    assert got["checks"]["must_fire"]["missing"] == ["1"]


def test_an_unparseable_verdict_fails_the_parsed_check():
    rec = {"kind": "judge_round", "outcome": "failed", "wall_sec": 3.0,
           "driver_result": {"rounds": [{"verdict": None, "err": "no json"}]}}
    got = std.score("judge_round", {"verdict": "pass", "parsed": True}, rec)
    assert not got["ok"] and got["checks"]["parsed"]["got"] is False


def test_a_daemon_item_is_scored_on_what_the_run_produced_and_its_wall():
    rec = {"kind": "daemon", "outcome": "success", "wall_sec": 900.0,
           "driver_result": {"produced": {"proved": 2, "revisions": 1}}}
    exp = {"outcome": "success", "proved_at_least": 1,
           "wall_sec_at_most": 1800}
    assert std.score("daemon", exp, rec)["ok"]
    assert not std.score("daemon", {**exp, "proved_at_least": 3}, rec)["ok"]
    assert not std.score("daemon", {**exp, "wall_sec_at_most": 60}, rec)["ok"]


def test_a_provider_probe_is_scored_on_the_tools_its_spawn_actually_called(
        tmp_path):
    """Not on the brick's comment lines — those are a courtesy to the
    reader. The measurement is the spawn's own record: the providers'
    transcripts and the gateway's per-call log, both copied into `_out/`
    before the workspace goes."""
    out = tmp_path / "_out"
    (out / "transcripts" / "codex" / "p1").mkdir(parents=True)
    (out / "transcripts" / "codex" / "p1" / "rollout.jsonl").write_text(
        '{"name":"asterism_tools__compute"}\n'
        '{"name":"asterism_tools__loogle"}\n', encoding="utf-8")
    (out / "transcripts" / "claude").mkdir(parents=True)
    (out / "transcripts" / "claude" / "s.jsonl").write_text(
        '{"name":"mcp__asterism_tools__inspect"}\n', encoding="utf-8")
    (out / "mcp_logs").mkdir(parents=True)
    (out / "mcp_logs" / "p1.jsonl").write_text(
        json.dumps({"event": "tool_call", "name": "validate_file"}) + "\n",
        encoding="utf-8")
    assert std.tools_seen(out) >= {"compute", "loogle", "inspect",
                                   "validate_file"}
    rec = {"kind": "daemon", "outcome": "success", "wall_sec": 10.0,
           "driver_result": {"produced": {"proved": 1}}, "out_dir": str(out)}
    exp = {"outcome": "success", "proved_at_least": 1,
           "tools_touched": ["compute", "loogle", "inspect", "validate_file"]}
    assert std.score("daemon", exp, rec)["ok"]
    short = std.score(
        "daemon", {**exp, "tools_touched": ["compute", "goal_at"]}, rec)
    assert not short["ok"]
    assert short["checks"]["tools_touched"]["missing"] == ["goal_at"]


def test_a_theory_item_is_scored_on_the_documents_verdict_and_its_rounds():
    rec = {"kind": "theory_wake", "outcome": "success", "wall_sec": 400.0,
           "driver_result": {"theory_document": {"status": "accepted",
                                                 "rounds": 2}}}
    assert std.score("theory_wake", {"document": "accepted",
                                     "rounds_at_most": 3}, rec)["ok"]
    assert not std.score("theory_wake", {"document": "accepted",
                                         "rounds_at_most": 1}, rec)["ok"]
    assert not std.score("theory_wake", {"document": "rejected"}, rec)["ok"]


def test_a_gauntlet_is_scored_on_how_many_bricks_came_back_proved():
    rec = {"kind": "gauntlet", "outcome": "success", "wall_sec": 60.0,
           "driver_result": {"bricks": [{"slug": "a", "ok": True},
                                        {"slug": "b", "ok": False}]}}
    assert std.score("gauntlet", {"bricks_at_least": 1}, rec)["ok"]
    assert not std.score("gauntlet", {"bricks_at_least": 2}, rec)["ok"]


# ---------------------------------------------------------------------
# the scorecard
# ---------------------------------------------------------------------

def test_the_scorecard_gets_one_row_per_item_and_one_header_ever(tmp_path):
    """`<root>/scorecard.md` is the ONLY file under the lab root the
    runner writes outside `runs/`. It is appended to, never rewritten:
    the cross-model baselines a set is read against are the rows already
    in it."""
    rec = {"kind": "judge_round", "wall_sec": 9.0,
           "seats": {"adversary": {"provider": "codex", "model": "gpt-5"}},
           "prompt_sha256": {"adversary/adversary.md": "abc123" + "0" * 58}}
    exp = {"verdict": "rebut", "must_fire": ["1"], "must_not_fire": ["2"]}
    got = std.score("judge_round", exp, {**rec, "driver_result": {
        "rounds": [{"verdict": {"verdict": "rebut", "criteria": {
            "1": ["fired: a table"], "2": ["clear: argued"]}}}]}})
    for _ in range(2):
        std.append_scorecard(
            tmp_path, name="traps/cheap", kind="judge_round", record=rec,
            record_path=(tmp_path / "runs" / "standard" / "x"
                         / "run_record.json"),
            expected=exp, score=got)
    text = (tmp_path / std.SCORECARD_BASENAME).read_text(encoding="utf-8")
    assert text.count("| date |") == 1, "the header is written once"
    assert text.count("| traps/cheap |") == 2, "one row per item, appended"
    assert "abc123" in text and "codex/gpt-5" in text
    # A criterion list is unreadable unlabelled: `must_fire=["1"]` and
    # `must_not_fire=["1"]` would look identical and mean opposite
    # things.
    assert 'must_fire=fired ["1"]' in text
    assert "must_not_fire=ok" in text


# ---------------------------------------------------------------------
# the gauntlet's bricks
# ---------------------------------------------------------------------

def test_the_gauntlet_refuses_an_empty_brick_directory(tmp_path):
    """"Refuses with a message naming what it needs" — the old harness
    picked its ten bricks by querying the live DB for proved union_closed
    theorems and stripping them, which is exactly the ad-hoc path this
    port drops. With nothing under `sets/gauntlet/bricks/` there is no
    exam, and inventing one is how a gauntlet comes to measure a
    different set of bricks per run."""
    empty = tmp_path / "bricks"
    empty.mkdir()
    with pytest.raises(LabError) as exc:
        gauntlet_mod.load_bricks(empty)
    assert "bricks" in str(exc.value) and "single" in str(exc.value).lower()


def test_a_brick_is_one_decl_with_its_proof_replaced_by_sorry(tmp_path):
    """The old harness's semantics, kept: single-decl files only, the
    head up to `:=` preserved verbatim (signature EXACTLY as given), the
    trailing `end` lines carried over."""
    d = tmp_path / "bricks"
    d.mkdir()
    (d / "one.lean").write_text(
        "import Mathlib\nnamespace P\n\ntheorem foo : 1 + 1 = 2 := by\n"
        "  norm_num\n\nend P\n", encoding="utf-8")
    (d / "two.lean").write_text(
        "theorem a : True := trivial\ntheorem b : True := trivial\n",
        encoding="utf-8")
    bricks = gauntlet_mod.load_bricks(d)
    assert [b.slug for b in bricks] == ["one"], "two decls is not a brick"
    assert bricks[0].stub.endswith("end P\n")
    assert ":= by\n  sorry" in bricks[0].stub
    assert "theorem foo : 1 + 1 = 2" in bricks[0].stub


def test_a_candidate_carrying_sorry_or_an_axiom_never_reaches_the_compiler():
    for bad in ("theorem a : True := by sorry\n",
                "theorem a : True := by admit\n",
                "axiom a : True\n"):
        assert gauntlet_mod.reject(bad), \
            f"{bad!r} must be rejected before `lake env lean`"
    assert not gauntlet_mod.reject("theorem a : True := trivial\n")


def test_the_lean_answer_is_taken_out_of_a_fenced_block_when_there_is_one():
    assert gauntlet_mod.extract_lean(
        "here you go\n```lean\ntheorem a : True := trivial\n```\n"
    ).strip() == "theorem a : True := trivial"
    assert gauntlet_mod.extract_lean("theorem a : True := trivial\n").strip() \
        == "theorem a : True := trivial"


# ---------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------

def _fake_launch(result: dict):
    def launch(ws: Path, spec_path: Path):
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        out = Path(spec["out"])
        out.mkdir(parents=True, exist_ok=True)
        (out / driver_mod.RESULT_BASENAME).write_text(
            json.dumps(result), encoding="utf-8")
        return 0, 1.0
    return launch


@pytest.fixture(scope="module")
def head() -> str:
    import subprocess
    return subprocess.run(["git", "-C", str(lab.REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True,
                          check=True).stdout.strip()


@pytest.fixture(scope="module")
def base(tmp_path_factory, head) -> Path:
    return build_mod.ensure_base(tmp_path_factory.mktemp("labroot"), head)


def _copy_base(base: Path, root: Path) -> Path:
    """`ensure_base` without the `git archive` — the module-scoped one is
    taken once for the whole file."""
    import shutil
    dst = lab.base_dir(root)
    if not dst.exists():
        shutil.copytree(base, dst,
                        ignore=shutil.ignore_patterns("__pycache__"))
        build_mod.seed_base_problems(root, dst)
    return dst


def test_running_one_item_scores_it_and_appends_exactly_one_row(
        tmp_path, base, monkeypatch):
    """One workspace per ITEM, and the score lands in the record — the
    workspace is gone by the time anyone reads it, so a score derived
    later would have nothing to derive it from."""
    _sets(tmp_path)
    monkeypatch.setattr(build_mod, "ensure_base",
                        lambda root, commit: _copy_base(base, root))
    rows = std.run(tmp_path, "traps/cheap", workspace=tmp_path / "live",
                   launch=_fake_launch({
                       "outcome": "success",
                       "rounds": [{"verdict": {
                           "verdict": "rebut",
                           "criteria": {"1": ["fired: a table"],
                                        "2": ["clear: argued"]}}}]}))
    assert len(rows) == 1 and rows[0]["score"]["ok"]
    rec = json.loads(Path(rows[0]["record_path"]).read_text(encoding="utf-8"))
    assert rec["score"]["ok"] is True
    assert rec["standard_item"] == "traps/cheap"
    card = (tmp_path / std.SCORECARD_BASENAME).read_text(encoding="utf-8")
    assert card.count("| traps/cheap |") == 1


def test_a_seat_override_reaches_every_item_of_the_run(tmp_path, base,
                                                       monkeypatch):
    _sets(tmp_path)
    monkeypatch.setattr(build_mod, "ensure_base",
                        lambda root, commit: _copy_base(base, root))
    seen: "list[Path]" = []

    def launch(ws: Path, spec_path: Path):
        seen.append(Path(ws))
        return _fake_launch({"outcome": "success", "rounds": []})(ws,
                                                                  spec_path)

    std.run(tmp_path, "traps/cheap", workspace=tmp_path / "live",
            seats={"adversary": "codex/gpt-5:xhigh"}, keep=True, launch=launch)
    import yaml
    cfg = yaml.safe_load((seen[0] / "Asterism.yaml").read_text(
        encoding="utf-8"))
    assert cfg["adversary"]["provider"] == "codex"
    assert cfg["adversary"]["reasoning_effort"] == "xhigh"


def _live_workspace(tmp_path: Path) -> Path:
    """A stand-in for the LIVE workspace, holding the one problem the
    table's `reuse_workspace_problems` names."""
    from Tooling.state import db as _db
    ws = tmp_path / "live"
    (ws / "Problems").mkdir(parents=True)
    conn = _db.connect(ws / "asterism.db")
    _db.init_schema(conn)
    conn.execute("INSERT OR IGNORE INTO projects (name, created_at)"
                 " VALUES ('Test', '2026-08-25T12:00:00+00:00')")
    conn.execute("INSERT INTO problems (name, created_at, project,"
                 " bootstrap_done) VALUES ('Test.provider_probe',"
                 " '2026-08-25T12:00:00+00:00', 'Test', 1)")
    groups_mod.ensure_top_group(conn, "Test.provider_probe", charter="probe")
    pdir = _db.problem_dir(ws, "Test.provider_probe")
    (pdir / "proofs").mkdir(parents=True)
    conn.commit()
    conn.close()
    return ws


def test_an_item_whose_problem_lives_in_the_workspace_arrives_as_a_slice(
        tmp_path, base, monkeypatch):
    """Two halves of the base meeting: the seeded Lab problems are
    already registered in it, and a reused problem's scene lands on top
    through `carry import`. A slice is TAKEN once and then reused —
    `snapshot.ensure_slice` re-takes an un-rewound one every call, which
    would give each item of a run a different scene."""
    _sets(tmp_path)
    monkeypatch.setattr(build_mod, "ensure_base",
                        lambda root, commit: _copy_base(base, root))
    live = _live_workspace(tmp_path)
    for _ in range(2):
        std.run(tmp_path, "smoke/provider_probe", workspace=live, keep=True,
                launch=_fake_launch({"outcome": "success",
                                     "produced": {"proved": 1}}))
    slices = [s.id for s in __import__(
        "Tooling.lab.snapshot", fromlist=["x"]).list_slices(tmp_path)]
    assert len(slices) == 1, f"one slice, reused: {slices}"
    ws = lab.runs_dir(tmp_path, std.EXPERIMENT_NAME) / "smoke_provider_probe_r1"
    conn = db.connect(ws / "asterism.db")
    try:
        have = {r["name"] for r in conn.execute("SELECT name FROM problems")}
    finally:
        conn.close()
    assert {"Lab.tiny", "Test.provider_probe"} <= have, \
        "the seeded problem AND the imported slice"


def test_an_unknown_target_names_the_sets_and_items_there_are(tmp_path):
    _sets(tmp_path)
    with pytest.raises(LabError) as exc:
        std.run(tmp_path, "traps/nope", workspace=tmp_path / "live")
    assert "traps/cheap" in str(exc.value)
