"""`asterism lab build` — the WORKSPACE, and the `lab.yaml` that
declares it.

A lab workspace is throwaway and never writes the live one: the base
skeleton, the slice landed with `carry import`, `Tooling/` from a NAMED
COMMIT (never the working tree — an experiment whose code is "whatever
was unsaved at launch" cannot be re-run), the arm's prompt and seat
overlay, and the heavy read-only trees linked rather than copied.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from Tooling import lab
from Tooling.lab import build as build_mod
from Tooling.lab import snapshot as snap_mod
from Tooling.lab import spec as spec_mod
from Tooling.state import db, groups as groups_mod

BEFORE = "2026-08-25T12:00:00+00:00"
PROBLEM = "Erdos.p1"


# ---------------------------------------------------------------------
# lab.yaml
# ---------------------------------------------------------------------

def _write_yaml(root: Path, exp: str, body: str) -> Path:
    d = lab.docs_dir(root, exp)
    d.mkdir(parents=True, exist_ok=True)
    (d / "lab.yaml").write_text(body, encoding="utf-8")
    return d / "lab.yaml"


def test_lab_yaml_declares_a_slice_arms_and_their_drivers(tmp_path):
    _write_yaml(tmp_path, "e1", """
snapshot: Erdos.p1@20260826-041105Z
code_commit: deadbeef
reps: 2
arms:
  baseline:
    kind: judge_round
    group: 691
    rows: [1119, 1362]
  louder:
    kind: judge_round
    group: 691
    rows: [1119]
    seats:
      adversary: codex/gpt-5:xhigh
""")
    e = spec_mod.load(tmp_path, "e1")
    assert e.snapshot == "Erdos.p1@20260826-041105Z"
    assert e.code_commit == "deadbeef" and e.reps == 2
    assert sorted(e.arms) == ["baseline", "louder"]
    assert e.arm("baseline").option("rows") == [1119, 1362]
    assert e.arm("louder").seats["adversary"] == {
        "provider": "codex", "model": "gpt-5", "reasoning_effort": "xhigh"}


def test_lab_yaml_refuses_a_mistyped_key(tmp_path):
    """The failure a lab.yaml is actually exposed to is not a crash: a
    `prompt:` where `prompts:` was meant runs the arm against the
    unedited prompt and looks like it worked. Unknown keys are refused,
    and the refusal names the keys that kind does take."""
    _write_yaml(tmp_path, "e1", """
snapshot: s1
arms:
  a:
    kind: judge_round
    group: 1
    rows: [1]
    prompt: overlays/a.md
""")
    with pytest.raises(lab.LabError) as exc:
        spec_mod.load(tmp_path, "e1")
    assert "prompt" in str(exc.value) and "prompts" in str(exc.value)


def test_lab_yaml_refuses_an_unknown_driver_kind(tmp_path):
    _write_yaml(tmp_path, "e1", """
snapshot: s1
arms:
  a: {kind: vibes, group: 1}
""")
    with pytest.raises(lab.LabError, match="vibes"):
        spec_mod.load(tmp_path, "e1")


def test_lab_yaml_names_exactly_one_slice(tmp_path):
    both = """
snapshot: s1
rewind: {problem: Erdos.p1, cutoff: "2026-08-26T04:11:05+00:00"}
arms:
  a: {kind: judge_round, group: 1, rows: [1]}
"""
    _write_yaml(tmp_path, "e1", both)
    with pytest.raises(lab.LabError, match="exactly one"):
        spec_mod.load(tmp_path, "e1")
    _write_yaml(tmp_path, "e2",
                "arms:\n  a: {kind: judge_round, group: 1, rows: [1]}\n")
    with pytest.raises(lab.LabError, match="exactly one"):
        spec_mod.load(tmp_path, "e2")


def test_lab_yaml_resolves_overlay_paths_beside_itself(tmp_path):
    """The lab's inputs live with the lab, never in the framework repo:
    a runner that reaches out of its own tree for the files it needs is
    re-runnable only on the machine that happens to hold them."""
    d = lab.docs_dir(tmp_path, "e1")
    (d / "overlays").mkdir(parents=True)
    (d / "overlays" / "adv.md").write_text("judge harder\n", encoding="utf-8")
    _write_yaml(tmp_path, "e1", """
snapshot: s1
arms:
  a:
    kind: judge_round
    group: 1
    rows: [1]
    prompts: {adversary/adversary.md: overlays/adv.md}
""")
    e = spec_mod.load(tmp_path, "e1")
    assert e.arm("a").prompts["adversary/adversary.md"] == \
        (d / "overlays" / "adv.md").resolve()


def test_lab_yaml_refuses_an_overlay_file_that_is_not_there(tmp_path):
    _write_yaml(tmp_path, "e1", """
snapshot: s1
arms:
  a:
    kind: judge_round
    group: 1
    rows: [1]
    prompts: {adversary/adversary.md: overlays/missing.md}
""")
    with pytest.raises(lab.LabError, match="missing.md"):
        spec_mod.load(tmp_path, "e1")


def test_lab_yaml_refuses_a_theory_arm_with_no_objective(tmp_path):
    _write_yaml(tmp_path, "e1", """
snapshot: s1
arms:
  a: {kind: theory_wake, group: 1, request: {situation: "stuck"}}
""")
    with pytest.raises(lab.LabError, match="objective"):
        spec_mod.load(tmp_path, "e1")


def test_lab_yaml_refuses_an_unknown_stop_condition(tmp_path):
    _write_yaml(tmp_path, "e1", """
snapshot: s1
arms:
  a: {kind: daemon, stop: {bricks: 3}}
""")
    with pytest.raises(lab.LabError, match="bricks"):
        spec_mod.load(tmp_path, "e1")


# ---------------------------------------------------------------------
# the workspace
# ---------------------------------------------------------------------

def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "live"
    (ws / "Problems").mkdir(parents=True)
    conn = db.connect(ws / "asterism.db")
    db.init_schema(conn)
    conn.execute("INSERT OR IGNORE INTO projects (name, created_at)"
                 " VALUES ('Erdos', ?)", (BEFORE,))
    conn.execute("INSERT INTO problems (name, created_at, project,"
                 " bootstrap_done) VALUES (?, ?, 'Erdos', 1)",
                 (PROBLEM, BEFORE))
    groups_mod.ensure_top_group(conn, PROBLEM, charter="c")
    pdir = db.problem_dir(ws, PROBLEM)
    (pdir / "proofs").mkdir(parents=True)
    db.insert_goal(conn, problem=PROBLEM, slug="main",
                   lean_path=(pdir / "Root.lean").relative_to(ws).as_posix(),
                   statement="True", origin="root", status="open")
    (pdir / "Root.lean").write_text("theorem main : True := trivial\n",
                                    encoding="utf-8")
    conn.commit()
    conn.close()
    return ws


@pytest.fixture(scope="module")
def head() -> str:
    out = subprocess.run(["git", "-C", str(lab.REPO), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


@pytest.fixture(scope="module")
def base(tmp_path_factory, head) -> Path:
    """One archived skeleton for the whole module — `git archive` of
    `Tooling/` is the expensive half of a build."""
    return build_mod.ensure_base(tmp_path_factory.mktemp("labroot"), head)


def _exp(root: Path, slice_id: str, *, arm_body: str = "") -> spec_mod.Experiment:
    _write_yaml(root, "e1", f"""
snapshot: {slice_id}
arms:
  a:
    kind: judge_round
    group: 1
    rows: [1]
{arm_body}
""")
    return spec_mod.load(root, "e1")


def test_base_is_an_empty_but_valid_workspace_skeleton(base):
    """The template every build starts from: the Lean project files and
    the four trees, with no problems in it. Its `Tooling/` comes from a
    commit, so what the skeleton holds is a fact about the repo rather
    than about the operator's unsaved edits."""
    for rel in ("Asterism.yaml", "lakefile.lean", "lake-manifest.json",
                "lean-toolchain", "Problems/README.md"):
        assert (base / rel).is_file(), rel
    for rel in ("Asterism", "Library", "Benchmarks", "Tooling/prompts"):
        assert (base / rel).is_dir(), rel
    assert not (base / "asterism.db").exists()
    assert not (base / ".git").exists()


def test_build_lands_the_slice_and_records_what_it_built(tmp_path, base,
                                                         head, monkeypatch):
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, tmp_path / "lab", problem=PROBLEM)
    exp = _exp(tmp_path / "lab", sl.id)
    ws = build_mod.build(tmp_path / "lab", exp, "a", slice_=sl,
                         base=base, commit=head, rep=1)
    conn = db.connect(ws / "asterism.db")
    try:
        assert [r[0] for r in conn.execute("SELECT name FROM problems")] == \
            [PROBLEM]
    finally:
        conn.close()
    assert (ws / "Problems" / "Erdos" / "p1" / "Root.lean").is_file()
    rec = json.loads((ws / "workspace.json").read_text(encoding="utf-8"))
    assert rec["slice"] == sl.id and rec["commit"] == head
    assert rec["arm"] == "a" and rec["experiment"] == "e1"
    assert "links" in rec


def test_build_never_puts_a_git_directory_in_the_workspace(tmp_path, base,
                                                           head):
    """Ten concurrent `git status` calls on the live index is what a
    `.git` link buys, and `agent.runtime._repo_status` degrades to "not
    a repo" under it — the artifact audit is not what any of these
    experiments measures."""
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, tmp_path / "lab", problem=PROBLEM)
    exp = _exp(tmp_path / "lab", sl.id)
    ws = build_mod.build(tmp_path / "lab", exp, "a", slice_=sl,
                         base=base, commit=head, rep=1)
    for rel in build_mod.FORBIDDEN:
        assert not (ws / rel).exists() and not (ws / rel).is_symlink(), rel


def test_build_refuses_a_target_a_daemon_owns(tmp_path, base, head):
    """`daemon.pid` means the directory is somebody's live workspace.
    Rebuilding one wipes a running board."""
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, tmp_path / "lab", problem=PROBLEM)
    exp = _exp(tmp_path / "lab", sl.id)
    target = lab.runs_dir(tmp_path / "lab", "e1") / "a_r1"
    (target / ".asterism").mkdir(parents=True)
    (target / ".asterism" / "daemon.pid").write_text("4242 0.0",
                                                     encoding="utf-8")
    with pytest.raises(lab.LabError, match="daemon"):
        build_mod.build(tmp_path / "lab", exp, "a", slice_=sl,
                        base=base, commit=head, rep=1)


def test_build_migrates_a_slice_taken_on_an_older_schema(tmp_path, base,
                                                         head):
    """The 1119 lesson: a snapshot older than the current schema is a
    snapshot whose workspace cannot be opened. The bundle is never
    written — a COPY is migrated up on the way in, which is `carry
    import --allow-migrate`'s whole job."""
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, tmp_path / "lab", problem=PROBLEM)
    import sqlite3
    c = sqlite3.connect(sl.path / "carry.db")
    current = int(c.execute("PRAGMA user_version").fetchone()[0])
    c.execute(f"PRAGMA user_version = {current - 1}")
    c.commit()
    c.close()
    exp = _exp(tmp_path / "lab", sl.id)
    ws = build_mod.build(tmp_path / "lab", exp, "a", slice_=sl,
                         base=base, commit=head, rep=1)
    c = sqlite3.connect(ws / "asterism.db")
    try:
        assert int(c.execute("PRAGMA user_version").fetchone()[0]) == current
    finally:
        c.close()


def test_the_workspace_shares_the_dependency_tree_but_not_the_build_tree(
        tmp_path, base, head, monkeypatch):
    """`.lake/packages` is Mathlib and friends — 6.8 GB, built once,
    only read once built, and the difference between a lab run starting
    now and a lab run starting tomorrow. `.lake/build` is the LIVE
    workspace's own output: 78 GB of it, written by the daemon that is
    running right now, under lake's own lock.

    Sharing the whole `.lake` would put a lab `lake build` inside that —
    writing this experiment's oleans into the live tree and contending
    for its lock. So the dependency tree is linked and the build tree is
    the workspace's own, which costs a cold build of this problem's
    modules and is the correct price."""
    live = _workspace(tmp_path)
    fake_repo = tmp_path / "repo"
    (fake_repo / ".lake" / "packages" / "mathlib").mkdir(parents=True)
    (fake_repo / ".lake" / "packages" / "mathlib" / "x.olean").write_text(
        "shared", encoding="utf-8")
    (fake_repo / ".lake" / "build" / "lib").mkdir(parents=True)
    monkeypatch.setattr(build_mod, "REPO", fake_repo)
    sl = snap_mod.take(live, tmp_path / "lab", problem=PROBLEM)
    exp = _exp(tmp_path / "lab", sl.id)
    ws = build_mod.build(tmp_path / "lab", exp, "a", slice_=sl,
                         base=base, commit=head, rep=1)
    pkgs = ws / ".lake" / "packages"
    assert (pkgs / "mathlib" / "x.olean").is_file(), "the deps are reachable"
    assert pkgs.is_symlink() or pkgs.is_junction(), "…and shared, not copied"
    assert not (ws / ".lake" / "build").is_symlink(), \
        "the build tree is never the live one"
    rec = json.loads((ws / "workspace.json").read_text(encoding="utf-8"))
    assert rec["links"][".lake/packages"] in ("link", "copy")


def test_clearing_a_workspace_unlinks_the_shared_tree_it_does_not_own(
        tmp_path):
    """`.lake` is a JUNCTION into the framework's own build tree — 20 GB
    of Mathlib oleans that every lab workspace shares. Clearing a
    workspace by walking it must therefore unlink that entry rather than
    descend into it: a delete that followed the link would take the
    live tree with it, and the next `lake build` anywhere on the box
    would be a cold one.

    Python's `rmtree` has not followed a junction since 3.8; this pins
    the invariant to the lab's own cleanup, where a future `onerror=`
    or a `copy` fallback could reintroduce it."""
    ws = tmp_path / "ws"
    (ws / ".attempts").mkdir(parents=True)
    (ws / ".lake").mkdir()
    (ws / "keep.txt").write_text("x", encoding="utf-8")
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "precious.olean").write_text("do not delete", encoding="utf-8")
    # NESTED, the way a real workspace has it: `.lake/` is the
    # workspace's own directory and only `packages` inside it is shared.
    build_mod._link_or_copy(shared, ws / ".lake" / "packages")

    build_mod.clear_workspace(ws, keep=("keep.txt",))

    assert (shared / "precious.olean").is_file(), \
        "the shared tree the junction points at survived"
    assert not (ws / ".lake").exists()
    assert not (ws / ".attempts").exists()
    assert (ws / "keep.txt").is_file(), "kept entries stay"


# ---------------------------------------------------------------------
# the overlay
# ---------------------------------------------------------------------

def test_an_overlay_prompt_must_replace_one_the_workspace_already_has(
        tmp_path, base, head):
    """An overlay file that creates a NEW file is an overlay whose
    target moved — it would run the arm against the unedited prompt
    while looking like it worked."""
    root = tmp_path / "lab"
    d = lab.docs_dir(root, "e1")
    (d / "overlays").mkdir(parents=True)
    (d / "overlays" / "x.md").write_text("edited\n", encoding="utf-8")
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, root, problem=PROBLEM)
    exp = _exp(root, sl.id,
               arm_body="    prompts: {adversary/moved.md: overlays/x.md}")
    with pytest.raises(lab.LabError, match="replaces nothing"):
        build_mod.build(root, exp, "a", slice_=sl, base=base, commit=head,
                        rep=1)


def test_an_overlay_identical_to_the_live_prompt_is_refused(
        tmp_path, base, head):
    """A byte-identical overlay makes the arm a control while the report
    calls it a variant."""
    root = tmp_path / "lab"
    d = lab.docs_dir(root, "e1")
    (d / "overlays").mkdir(parents=True)
    same = (base / "Tooling" / "prompts" / "adversary" / "adversary.md"
            ).read_bytes()
    (d / "overlays" / "x.md").write_bytes(same)
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, root, problem=PROBLEM)
    exp = _exp(root, sl.id,
               arm_body="    prompts: {adversary/adversary.md: overlays/x.md}")
    with pytest.raises(lab.LabError, match="byte-identical"):
        build_mod.build(root, exp, "a", slice_=sl, base=base, commit=head,
                        rep=1)


def test_an_overlay_replaces_the_workspaces_own_prompt(tmp_path, base, head):
    root = tmp_path / "lab"
    d = lab.docs_dir(root, "e1")
    (d / "overlays").mkdir(parents=True)
    (d / "overlays" / "x.md").write_text("judge harder\n", encoding="utf-8")
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, root, problem=PROBLEM)
    exp = _exp(root, sl.id,
               arm_body="    prompts: {adversary/adversary.md: overlays/x.md}")
    ws = build_mod.build(root, exp, "a", slice_=sl, base=base, commit=head,
                         rep=1)
    assert (ws / "Tooling" / "prompts" / "adversary" / "adversary.md"
            ).read_text(encoding="utf-8") == "judge harder\n"
    rec = json.loads((ws / "workspace.json").read_text(encoding="utf-8"))
    assert rec["overlay"]["prompts"] == ["Tooling/prompts/adversary/adversary.md"]


def test_a_seat_override_lands_in_the_workspaces_own_config(tmp_path, base,
                                                            head):
    """The seat is a property of the workspace, so it goes where the
    framework reads one — `Asterism.yaml` in the workspace — rather than
    into an environment the driver would have to remember to export."""
    import yaml
    root = tmp_path / "lab"
    live = _workspace(tmp_path)
    sl = snap_mod.take(live, root, problem=PROBLEM)
    exp = _exp(root, sl.id,
               arm_body="    seats: {adversary: codex/gpt-5:xhigh}")
    ws = build_mod.build(root, exp, "a", slice_=sl, base=base, commit=head,
                         rep=1)
    cfg = yaml.safe_load((ws / "Asterism.yaml").read_text(encoding="utf-8"))
    assert cfg["adversary"]["provider"] == "codex"
    assert cfg["adversary"]["model"] == "gpt-5"
    assert cfg["adversary"]["reasoning_effort"] == "xhigh"
    rec = json.loads((ws / "workspace.json").read_text(encoding="utf-8"))
    assert rec["overlay"]["seats"]["adversary"]["model"] == "gpt-5"
