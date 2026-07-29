"""Research mode P1 — the proposal-package gate + Adversary cycle
(research_mode_design.md §1/§3).

Covers: gate shape (exempt kinds / experiment rule),
the rebut→revise→pass round trip (dialogue recorded, rev advances,
fresh judge per round), exhaustion → strategist_proposal_rejected with
the discarded proposal + criticisms in programme_revisions, and the
projection's isolation-relevant contents. Mirrors
test_phase2_run_pipelines fixtures (mocked spawn_llm, everything else
real).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from Tooling import agent
from Tooling.pipeline import adversary, strategist
from Tooling.state import db, manifest, programme


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n\n## Statement\nT\n", encoding="utf-8")
    (pdir / "proofs").mkdir()
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at,"
        " bootstrap_done) VALUES ('p', 'Problems/p/Manifest.md', ?, 1)",
        (db.now(),),
    )
    c.commit()
    return c


@pytest.fixture
def mfst() -> manifest.Manifest:
    return manifest.Manifest(problem="p", statement="T")


def _insert_root(conn: sqlite3.Connection) -> int:
    return db.insert_goal(
        conn, problem="p", slug="main",
        lean_path="Problems/p/Root.lean", statement="T",
        origin="root", depth=0,
    )


def _d(kind: str, **kw) -> SimpleNamespace:
    return SimpleNamespace(kind=kind, pipeline=kw.get("pipeline"),
                           target_id=kw.get("target_id"),
                           brief=kw.get("brief"), body=kw.get("body"),
                           reason=kw.get("reason"))


_PROPOSAL = ("# Step\n## Argument\nWhy this batch.\n"
             "## Proof\nThe route holds.\n## Roadmap\n1. the brick\n")


# -------------------------------------------------------------- gate

def test_gate_shape():
    assert not strategist.package_gate_applies(
        [_d("FetchPaper"), _d("Noop")], "routine")
    assert not strategist.package_gate_applies(
        [_d("RequestUserAmend")], "pending_review")
    # Any route-moving kind arms the gate — including EmitDirective
    # (the drift side door) and the endgame kinds.
    for kind in ("Inject", "AttemptDisproof", "ConfirmShelve",
                 "MarkDeliverable", "Ingest", "EmitDirective"):
        assert strategist.package_gate_applies(
            [_d(kind), _d("Noop")], "routine"), kind


def test_package_requires_file_and_experiment(tmp_path: Path):
    body, sections, err = strategist.verify_proposal_package(
        [_d("Inject", pipeline="Forward", brief="b")], tmp_path)
    assert body is None and "proposal.md" in err

    (tmp_path / "proposal.md").write_text(_PROPOSAL, encoding="utf-8")
    # EmitDirective-only (no experiment, not endgame) → rejected.
    body, sections, err = strategist.verify_proposal_package(
        [_d("EmitDirective", body="x")], tmp_path)
    assert body is None and "experiment" in err
    # Endgame batches are exempt from the experiment rule.
    body, sections, err = strategist.verify_proposal_package(
        [_d("Ingest")], tmp_path)
    assert err is None and body == _PROPOSAL
    # AttemptDisproof counts as the experiment (no brief → no tag rule).
    body, sections, err = strategist.verify_proposal_package(
        [_d("AttemptDisproof")], tmp_path)
    assert err is None
    # Inject briefs must name an existing Roadmap entry (P2 check).
    body, sections, err = strategist.verify_proposal_package(
        [_d("Inject", brief="## Need\nx")], tmp_path)
    assert body is None and "Roadmap:" in err
    body, sections, err = strategist.verify_proposal_package(
        [_d("Inject", brief="Roadmap: no such entry\n## Need\nx")],
        tmp_path)
    assert body is None and "no such entry" in err
    body, sections, err = strategist.verify_proposal_package(
        [_d("Inject", brief="Roadmap: the brick\n## Need\nx")], tmp_path)
    assert err is None


# ------------------------------------------------- verdict contract

def _criteria(**fired: str) -> dict:
    """All-clear criteria dict, with named criteria fired."""
    c = {k: "clear" for k in adversary.CRITERIA_KEYS}
    for k, reason in fired.items():
        c[k.lstrip("c")] = f"fired: {reason}"
    return c


def test_parse_verdict_derives_ruling():
    """2026-07-25: the verdict is DERIVED — any fired criterion = rebut,
    all clear = pass. Five instances across three b6_1 legs of a judge
    documenting a defect and passing anyway; the pass/rebut decision is
    no longer the model's to write."""
    v, err = adversary.parse_verdict(
        json.dumps({"criteria": _criteria()}))
    assert err == "" and v["verdict"] == "pass"
    assert v["reservations"] == [] and v["criticisms"] == []

    v, err = adversary.parse_verdict(json.dumps(
        {"criteria": _criteria(c3="weak step 5"),
         "reservations": ["note"]}))
    assert err == "" and v["verdict"] == "rebut"
    assert v["criticisms"] == ["[criterion 3] weak step 5"]
    assert v["reservations"] == ["note"]


def test_parse_verdict_contract():
    for bad in (
            "not json", json.dumps(["x"]),
            json.dumps({"verdict": "pass"}),               # legacy shape
            json.dumps({"criteria": "all clear"}),
            json.dumps({"criteria": {k: "clear" for k in "1234"}}),
            json.dumps({"criteria": {**_criteria(), "2": "fired:"}}),
            json.dumps({"criteria": {**_criteria(), "3": "maybe"}}),
            json.dumps({"criteria": _criteria(),
                        "reservations": [1]})):
        v, err = adversary.parse_verdict(bad)
        assert v is None and err


# ------------------------------------- full cycle via run_strategist

def _spawn_script(rebuttals_before_pass: int):
    """A scripted spawn_llm: the strategist writes an Inject batch +
    proposal (revising the title per round); the adversary rebuts N
    times, then passes with one reservation. Captures adversary
    session ids to assert fresh-per-round."""
    state = {"adversary_calls": 0, "adversary_sids": [],
             "strategist_calls": 0}

    def fake_spawn(**kw):
        if kw.get("kind") == "adversary":
            state["adversary_calls"] += 1
            state["adversary_sids"].append(kw.get("session_id"))
            if state["adversary_calls"] <= rebuttals_before_pass:
                verdict = {"criteria": _criteria(
                    c2=f"objection {state['adversary_calls']}")}
            else:
                verdict = {"criteria": _criteria(),
                           "reservations": ["watch the sign"]}
            (kw["attempts_dir"] / "verdict.json").write_text(
                json.dumps(verdict), encoding="utf-8")
            return 0
        state["strategist_calls"] += 1
        n = state["strategist_calls"]
        (kw["attempts_dir"] / "decision.json").write_text(
            json.dumps({"kind": "Inject", "pipeline": "Forward",
                        "brief": f"Roadmap: the brick\n## Need\nbrick v{n}"}),
            encoding="utf-8")
        (kw["attempts_dir"] / "proposal.md").write_text(
            _PROPOSAL.replace("# Step", f"# Step v{n}"),
            encoding="utf-8")
        return 0

    return fake_spawn, state


def test_rebut_then_pass_advances_rev(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_root(conn)
    fake, state = _spawn_script(rebuttals_before_pass=1)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=1,
        workspace=workspace, mfst=mfst, pipeline_id="adv-1",
    )
    assert r.outcome == "success"
    # One rebuttal round: 2 strategist spawns, 2 adversary spawns,
    # each adversary round on a FRESH session id.
    assert state["strategist_calls"] == 2
    assert state["adversary_calls"] == 2
    assert len(set(state["adversary_sids"])) == 2

    row = programme.current_rev(conn, "p")
    assert row is not None and row["rev"] == 1
    assert "# Step v2" in row["body"]  # the revised proposal passed
    assert row["rounds"] == 1
    assert row["batch_id"] is not None
    verdict = json.loads(row["verdict"])
    assert verdict["reservations"] == ["watch the sign"]
    dialogue = json.loads(row["dialogue"])
    assert dialogue[0]["criticisms"] == ["[criterion 2] objection 1"]
    assert "# Step v1" in dialogue[0]["proposal"]
    # Render landed beside the problem files.
    rendered = (workspace / "Problems" / "p" / "PROGRAMME.md")
    assert rendered.exists()
    assert "watch the sign" in rendered.read_text(encoding="utf-8")


def test_exhaustion_records_rejection(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_root(conn)
    monkeypatch.setenv("ASTERISM_STRATEGIST_VERIFY_RETRY", "2")
    fake, state = _spawn_script(rebuttals_before_pass=99)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=1,
        workspace=workspace, mfst=mfst, pipeline_id="adv-2",
    )
    assert r.outcome == "failed"
    assert r.failure_reason == "strategist_proposal_rejected"
    # No rev passed; the rejected row keeps proposal + full dialogue.
    assert programme.current_rev(conn, "p") is None
    row = conn.execute(
        "SELECT * FROM programme_revisions WHERE problem='p'"
        " AND status='rejected'").fetchone()
    assert row is not None and row["rounds"] == 2
    dialogue = json.loads(row["dialogue"])
    assert [e["criticisms"] for e in dialogue] == [
        ["[criterion 2] objection 1"], ["[criterion 2] objection 2"],
        ["[criterion 2] objection 3"]]
    # Next wake gets the one-line record, never the draft.
    notice = programme.rejection_notice(conn, "p")
    assert notice and "rejected" in notice
    # No commit happened: no strategist_decisions row for the batch,
    # and the stall anchor (last_strategist_at ratchet) did not move —
    # a rejected wake stays visible to the cross-wake no-delta
    # machinery (design §1: 被拒 wake 計入跨-wake 無 delta 序列).
    assert conn.execute(
        "SELECT COUNT(*) FROM strategist_decisions WHERE problem='p'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT last_strategist_at FROM problems WHERE name='p'"
    ).fetchone()[0] is None


def test_exempt_batch_skips_adversary(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Noop-only batch (wholly exempt kinds) never spawns the
    Adversary and needs no proposal.md."""
    _insert_root(conn)
    calls = {"adversary": 0}

    def fake_spawn(**kw):
        if kw.get("kind") == "adversary":
            calls["adversary"] += 1
            return 0
        (kw["attempts_dir"] / "decision.json").write_text(
            json.dumps({"kind": "Noop", "reason": "work in flight"}),
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=1,
        workspace=workspace, mfst=mfst, pipeline_id="adv-3",
    )
    assert r.failure_reason == "strategist_noop"
    assert calls["adversary"] == 0


# -------------------------------------------------- context surfaces

def test_context_surfaces(workspace: Path, conn: sqlite3.Connection):
    from Tooling.agent import context as wctx
    from Tooling.agent import phase2_context

    # Bootstrap: strategist sees the founding line; workers see nothing.
    boot = "\n".join(phase2_context._section_programme_strategist(conn, "p"))
    assert "rev 1" in boot and "none yet" in boot
    assert wctx._section_programme_worker(conn, "p", None) == []

    programme.record_pass(
        conn, "p", _PROPOSAL,
        {"verdict": "pass", "reservations": ["watch the sign"]},
        [], 1, "b1")
    s = "\n".join(phase2_context._section_programme_strategist(conn, "p"))
    assert "rev 1" in s and "## Proof" in s and "watch the sign" in s
    # NL-first worker premise (2026-07-25): the worker's share is the
    # full ## Proof + one pointer; reservations live behind the pointer
    # (PROGRAMME.md header), no longer inline.
    w = "\n".join(wctx._section_programme_worker(conn, "p", None))
    assert "## Proof" in w and "The route holds." in w
    assert "PROGRAMME.md" in w and "watch the sign" not in w

    # After a discarded cycle the strategist gets the one-line record.
    programme.record_rejection(conn, "p", _PROPOSAL, [], 3)
    s2 = "\n".join(phase2_context._section_programme_strategist(conn, "p"))
    assert "Previous proposal rejected" in s2

    # Dangling pointer heals: rev in DB, file gone → the worker
    # section re-renders idempotently before advertising it.
    pdir = workspace / "Problems" / "p"
    rendered = pdir / "PROGRAMME.md"
    if rendered.exists():
        rendered.unlink()
    w2 = "\n".join(wctx._section_programme_worker(conn, "p", None, pdir))
    assert "PROGRAMME.md" in w2
    assert rendered.exists()


# ------------------------------------------------------- projection

def test_projection_contents(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    attempts = workspace / ".attempts" / "adv-proj"
    attempts.mkdir(parents=True)
    pdir = workspace / "Problems" / "p"
    # CATALOG.md never lives in problem_dir — the projection generates
    # it from goal records (07-19: the old problem_dir copy was dead
    # code and the judge never saw the landed-brick list).
    db.insert_goal(
        conn, problem="p", slug="brick_a",
        lean_path="Problems/p/proofs/L_brick_a.lean",
        statement="theorem brick_a : 1 + 1 = 2", origin="forward",
        depth=1, status="proved")
    # formal ground truth rides along read-only (user call 07-19)
    (pdir / "Root.lean").write_text("theorem main : T := by sorry\n",
                                    encoding="utf-8")
    (pdir / "Defs.lean").write_text("def f := 1\n", encoding="utf-8")

    proj = adversary.build_projection(
        round_no=2, attempts_dir=attempts, problem_dir=pdir,
        conn=conn, problem="p", proposal_body=_PROPOSAL,
        decisions=[_d("Inject", pipeline="Forward", brief="## Need\nx")],
        dialogue=[{"round": 1, "role": "adversary",
                   "criticisms": ["too vague"], "proposal": "# old"}],
        proof_warn="WARN: long proof")

    assert proj == attempts / "adversary" / "r2"
    assert (proj / "Manifest.md").exists()
    cat = (proj / "CATALOG.md").read_text(encoding="utf-8")
    assert "brick_a" in cat and "Proved catalog" in cat
    assert (proj / "Root.lean").exists()
    assert (proj / "Defs.lean").exists()
    # PROGRAMME.md = current rev (bootstrap placeholder here) + its
    # execution record, welded into one file.
    prog = (proj / "PROGRAMME.md").read_text(encoding="utf-8")
    assert "rev 1" in prog
    assert "Completed Inject batches" in prog
    assert not (proj / "outcomes.md").exists()
    assert "WARN: long proof" in (proj / "proposal.md").read_text(
        encoding="utf-8")
    assert "Inject(Forward)" in (proj / "decisions.md").read_text(
        encoding="utf-8")
    d = (proj / "dialogue.md").read_text(encoding="utf-8")
    assert "too vague" in d and "# old" in d


# ---------------------------------------------------------------------
# spawn_usage attribution (invisible-judge class, 2026-07-18)
# ---------------------------------------------------------------------

def test_record_spawn_usage_explicit_attribution(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """The Adversary spawns into a projection dir nested inside another
    pipeline's attempts dir — layout-derived attribution pointed the
    workspace at `.attempts/<pid>/` and silently dropped every judge
    row (b6: ~0.5h invisible). Explicit params must land the row on the
    real problem, tied to the host strategist pipeline."""
    from Tooling.agent.runtime import _record_spawn_usage
    strategist_attempts = workspace / ".attempts" / "pid-strat-7"
    proj = strategist_attempts / "adversary" / "r3"
    proj.mkdir(parents=True)
    (proj / "_parser_state.json").write_text(
        json.dumps({"usage": {"turns": 4, "output_tokens": 1234,
                              "input_tokens": 56}}),
        encoding="utf-8")

    _record_spawn_usage(
        kind="adversary", attempts_dir=proj, problem_dir=proj,
        wall_sec=12.5, workspace=workspace, problem="p",
        pipeline_id=strategist_attempts.name)

    row = conn.execute("SELECT * FROM spawn_usage").fetchone()
    assert row is not None
    assert row["problem"] == "p"
    assert row["kind"] == "adversary"
    assert row["pipeline_id"] == "pid-strat-7"
    assert row["output_tokens"] == 1234


def test_record_spawn_usage_never_mints_a_junk_db(
    workspace: Path,
) -> None:
    """Without explicit params the old code derived a wrong workspace
    and `connect()` CREATED an empty sqlite file there. A derived
    workspace with no asterism.db must be a silent no-op, not a mint."""
    from Tooling.agent.runtime import _record_spawn_usage
    proj = workspace / ".attempts" / "pid-x" / "adversary" / "r1"
    proj.mkdir(parents=True)
    (proj / "_parser_state.json").write_text(
        json.dumps({"usage": {"turns": 1, "output_tokens": 9}}),
        encoding="utf-8")

    _record_spawn_usage(kind="adversary", attempts_dir=proj,
                        problem_dir=proj, wall_sec=1.0)

    # derived workspace = proj.parent.parent = .attempts/pid-x — the
    # guard must not have created an asterism.db there
    assert not (workspace / ".attempts" / "pid-x" / "asterism.db").exists()


def test_projection_catalog_matches_strategist_view_nested_problem(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """07-29 cube_e2e verdict war: for a DOMAIN-NESTED problem the
    projection derived workspace from problem_dir (fixed 2-level
    assumption) → the catalog's signature file-read silently fell back
    to the bare DB statement (`Prop` for a def), and the judge
    prosecuted the strategist's honest full-signature citation as
    fabrication for two rounds. Workspace must come from attempts_dir
    (fixed `<ws>/.attempts/<pid>` layout), not problem_dir (variable
    nesting) — and the projection CATALOG must equal the strategist's
    own companion byte for byte."""
    ndir = workspace / "Problems" / "Dom" / "nested"
    (ndir / "proofs").mkdir(parents=True)
    (ndir / "Manifest.md").write_text(
        "---\nproblem: Dom.nested\n---\n\n## Statement\nT\n",
        encoding="utf-8")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at,"
        " bootstrap_done) VALUES ('Dom.nested',"
        " 'Problems/Dom/nested/Manifest.md', ?, 1)", (db.now(),))
    full = "def is_cube (n : ℕ) : Prop := ∃ k, n = k ^ 3"
    (ndir / "proofs" / "L_is_cube.lean").write_text(
        "import Mathlib\n\nnamespace Problems.Dom.nested\n\n"
        + full + "\n\nend Problems.Dom.nested\n", encoding="utf-8")
    db.insert_goal(
        conn, problem="Dom.nested", slug="is_cube",
        lean_path="Problems/Dom/nested/proofs/L_is_cube.lean",
        statement="Prop", origin="forward", depth=1, kind="def",
        status="proved")
    conn.commit()
    attempts = workspace / ".attempts" / "adv-nested"
    attempts.mkdir(parents=True)

    proj = adversary.build_projection(
        round_no=1, attempts_dir=attempts, problem_dir=ndir,
        conn=conn, problem="Dom.nested", proposal_body=_PROPOSAL,
        decisions=[_d("Inject", brief="## Need\nx")],
        dialogue=[], proof_warn=None)
    cat = (proj / "CATALOG.md").read_text(encoding="utf-8")
    assert full in cat, f"projection catalog degraded to bare statement:\n{cat}"

    from Tooling.agent.context import write_catalog_companion
    sdir = workspace / ".attempts" / "strategist-side"
    sdir.mkdir(parents=True)
    write_catalog_companion(conn, "Dom.nested", sdir)
    assert (sdir / "CATALOG.md").read_text(encoding="utf-8") == cat


def test_projection_stages_tree_cited_proofs_and_directive_body(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """07-29 judge feedback batch: TREE.md rides along; landed proof
    files the package text cites are staged read-only; the directive
    BODY (payload['body'] on real Decisions — `.body` only ever existed
    on test fixtures) reaches decisions.md; goal targets are annotated
    (slug, status) since CATALOG carries names, not ids."""
    attempts = workspace / ".attempts" / "adv-stage"
    attempts.mkdir(parents=True)
    pdir = workspace / "Problems" / "p"
    (pdir / "TREE.md").write_text("# t\nmain  (frozen)\n", encoding="utf-8")
    (pdir / "proofs" / "L_cited_brick.lean").write_text(
        "def cited_brick : Prop := True\n", encoding="utf-8")
    (pdir / "proofs" / "L_unrelated.lean").write_text(
        "def unrelated : Prop := True\n", encoding="utf-8")
    gid = db.insert_goal(conn, problem="p", slug="tgt",
                         lean_path="Problems/p/proofs/L_tgt.lean",
                         statement="T", origin="forward", status="proved")
    conn.commit()
    decisions = [
        SimpleNamespace(kind="MarkDeliverable", pipeline=None,
                        target_id=gid, brief=None, body=None,
                        reason="mark it", payload={}),
        SimpleNamespace(kind="EmitDirective", pipeline=None,
                        target_id=None, brief=None, body=None,
                        reason="r", payload={"body": "DIRECTIVE BODY LINE"}),
    ]
    proj = adversary.build_projection(
        round_no=1, attempts_dir=attempts, problem_dir=pdir,
        conn=conn, problem="p",
        proposal_body=_PROPOSAL + "\nuses cited_brick in the argument",
        decisions=decisions, dialogue=[], proof_warn=None)
    assert (proj / "TREE.md").exists()
    assert (proj / "proofs" / "L_cited_brick.lean").exists()
    assert not (proj / "proofs" / "L_unrelated.lean").exists()
    dec = (proj / "decisions.md").read_text(encoding="utf-8")
    assert "DIRECTIVE BODY LINE" in dec
    assert f"→ {gid} (`tgt`, proved)" in dec


def test_adversary_contract_section_matches_wake_prompts() -> None:
    """07-29 (A): the judge carries a verbatim copy of the Strategist's
    decision-kind contract so quoted contract clauses are checkable
    inside the sandbox. Every bullet must exist byte-for-byte in one of
    the three wake prompts — editing a wake bullet without updating the
    judge's copy fails here."""
    import re as _re
    root = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"
    adv = (root / "adversary" / "adversary.md").read_text(encoding="utf-8")
    section = adv[adv.index("## The Strategist's contract"):
                  adv.index("## How to judge")]
    wakes = "".join(
        (root / "strategist" / f).read_text(encoding="utf-8")
        for f in ("routine.md", "inject_batch_done.md",
                  "pending_review.md"))
    body = section.split("\n\n`target_goal_id`")[0]
    blocks = _re.split(r"\n(?=- )", body)
    checked = 0
    for b in blocks[1:]:
        b = b.strip("\n")
        if not b.startswith("- "):
            continue
        assert b in wakes, (
            f"adversary contract bullet drifted from the wake prompts:\n"
            f"{b[:140]}")
        checked += 1
    assert checked >= 9, checked
    assert "`target_goal_id` accepts integer id or slug." in wakes


def test_plan_note_rewrite_step_synced_and_names_attempts_dir() -> None:
    """07-29 SG: the `Rewrite _plan.md` step named no location, and with
    cwd=problem_dir one strategist wrote the note to the problem root —
    persist_plan_note found nothing in the sandbox, so soft-cap telemetry
    and the next wake's plan-note context section silently vanished
    (cube_e2e same day: sandbox write, channel fine). The step must carry
    the same location convention as proposal.md / brief_file and stay
    byte-identical across the three wake prompts."""
    root = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"
    steps = []
    for f in ("routine.md", "inject_batch_done.md", "pending_review.md"):
        text = (root / "strategist" / f).read_text(encoding="utf-8")
        hits = [ln.lstrip("0123456789. ") for ln in text.splitlines()
                if "**Rewrite `_plan.md`**" in ln]
        assert len(hits) == 1, (f, hits)
        steps.append(hits[0])
    assert len(set(steps)) == 1, steps
    assert "bare filename, in your attempts dir" in steps[0]


def test_proposal_section_shared_lines_synced() -> None:
    """07-29 programme readback: both SG and cube strategists misread
    'Carry ≥1' as '≥1 AttemptDisproof per route-moving batch' (the gate
    counts Inject or AttemptDisproof — strategist._EXPERIMENT_KINDS) and
    paid a recurring defense paragraph in every revision; passed
    revisions also carried round-numbered concession narration. The
    corrective lines stay byte-identical across the three wake
    prompts."""
    root = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"
    texts = {
        f: (root / "strategist" / f).read_text(encoding="utf-8")
        for f in ("routine.md", "inject_batch_done.md",
                  "pending_review.md")}
    for needle in (
        "Every route-moving batch carries ≥1 experiment — an Inject or "
        "an AttemptDisproof",
        "Injects alone satisfy this — no defense needed",
        "**Write for the record, not the reviewer** — the passed "
        "revision outlives the cycle",
    ):
        for f, t in texts.items():
            assert needle in t, (f, needle)


def test_parse_verdict_tolerates_annotated_clear_and_fired() -> None:
    """07-29 third occurrence (2× b6_1 07-27, 1× SG): opus-tier judges
    annotate their verdicts — `"clear — I checked…"` — and the literal
    match discarded two full adversary rounds per hit, failing the
    whole wake as agent_no_output. Prefix-keyed with a word boundary:
    annotations tolerated, "clearly…" still malformed."""
    v, err = adversary.parse_verdict(json.dumps({"criteria": {
        "1": "clear — I checked the chain end to end",
        "2": "Clear",
        "3": "fired — the merge is not forced",
        "4": "fired: the Proof skips the boundary case",
        "5": "clear"}}))
    assert err == "" and v is not None
    assert v["verdict"] == "rebut"
    assert len(v["criticisms"]) == 2
    assert any("boundary case" in c for c in v["criticisms"])
    assert any("merge is not forced" in c for c in v["criticisms"])

    bad, err2 = adversary.parse_verdict(json.dumps({"criteria": {
        "1": "clearly fine", "2": "clear", "3": "clear",
        "4": "clear", "5": "clear"}}))
    assert bad is None and "criterion 1" in err2
