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
    return manifest.Manifest(problem="p", body="T")


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
    # (the drift side door) and Ingest, the terminal act.
    for kind in ("Inject", "ConfirmShelve", "Ingest", "EmitDirective"):
        assert strategist.package_gate_applies(
            [_d(kind), _d("Noop")], "routine"), kind
    # MarkDeliverable is exempt as of 2026-08-11, when it moved out of
    # the retired admin turn: it records that work already dispatched,
    # already argued and already kernel-checked is the deliverable, and
    # demanding a fresh Programme revision to say so would be friction
    # the un-judged admin turn never charged. Deliberate, not drift.
    assert not strategist.package_gate_applies(
        [_d("MarkDeliverable"), _d("Noop")], "routine")
    # …but a mark riding a batch that DOES move the route is gated with
    # it: the gate asks whether ANY kind is non-exempt.
    assert strategist.package_gate_applies(
        [_d("MarkDeliverable"), _d("Inject")], "routine")


def test_package_requires_file_but_no_experiment_quota(tmp_path: Path):
    body, sections, err = strategist.verify_proposal_package(
        [_d("Inject", pipeline="Forward", brief="b")], tmp_path)
    assert body is None and "proposal.md" in err

    (tmp_path / "proposal.md").write_text(_PROPOSAL, encoding="utf-8")
    # The ≥1-experiment quota retired 2026-08-16 (owner ruling): a
    # per-batch quota is satisfied with manufactured experiments —
    # measured on union_closed, 13 of 14 delivered groups' exit batches
    # carried a companion Inject to feed it — while the dead-air
    # invariant is enforced by the STATE-based gates in
    # verify_decisions. A no-experiment package now passes here.
    body, sections, err = strategist.verify_proposal_package(
        [_d("ConfirmShelve", target_id="g1")], tmp_path)
    assert err is None and body == _PROPOSAL
    body, sections, err = strategist.verify_proposal_package(
        [_d("Ingest")], tmp_path)
    assert err is None and body == _PROPOSAL
    body, sections, err = strategist.verify_proposal_package(
        [_d("Delegate", brief="settle the sub-claim")], tmp_path)
    assert err is None
    # The brief is prose the verifier does not read at all (2026-08-11):
    # with or without a `Roadmap:` line, with a phrase that matches the
    # Roadmap or one that does not, the package passes. Whether the
    # experiment tests the entry it claims is the Adversary's call under
    # criteria 1/4.
    for brief in ("## Need\nx",
                  "Roadmap: no such entry\n## Need\nx",
                  "Roadmap: the brick\n## Need\nx"):
        body, sections, err = strategist.verify_proposal_package(
            [_d("Inject", brief=brief)], tmp_path)
        assert err is None, f"verifier read the brief: {brief!r} -> {err}"


def test_the_verifier_no_longer_reads_the_brief_at_all(tmp_path: Path):
    """The last mechanical reader of the Inject brief is gone
    (2026-08-11). It began as a substring match of the cited phrase
    against the free-prose Roadmap — a gate detecting free text — and
    bounced whole batches five times over phrasing (2026-08-03 feedback
    #4). Narrowed to "some line begins `Roadmap:`", it could not fail a
    wrong batch and could still fail a right one. The correspondence is
    the Adversary's, under criteria 1/4."""
    (tmp_path / "proposal.md").write_text(
        "# Step\n## Argument\nWhy.\n## Proof\nHolds.\n"
        "## Roadmap\n1. **the brick** — brief-ready\n"
        "2. **the wall** — later\n", encoding="utf-8")
    body, _s, err = strategist.verify_proposal_package(
        [_d("Inject", brief="Roadmap: the brick, then some prose\n## Need\nx"),
         _d("Inject", target_id="g7", brief="## Need\ny"),
         _d("Inject", brief="## Need\nz")], tmp_path)
    assert err is None and body is not None


# ------------------------------------------------- verdict contract

def _criteria(**fired: str) -> dict:
    """All-clear criteria dict, with named criteria fired. The naming
    criterion carries its mandatory naming (#159: a bare clear there is
    malformed). Read from `adversary.NAMING_CRITERION` rather than
    written as "1": the criteria were renumbered on 2026-08-13 and a
    hard-coded number here would have made six tests assert yesterday's
    contract."""
    c = {k: "clear" for k in adversary.CRITERIA_KEYS}
    c[adversary.NAMING_CRITERION] = (
        "clear: the closer entry — one prerequisite stands")
    for k, reason in fired.items():
        c[k.lstrip("c")] = f"fired: {reason}"
    return c


def _clear_criteria_json() -> str:
    """Minimal valid all-clear verdict.json for spawn stubs."""
    return json.dumps({"criteria": _criteria()})


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


def test_criterion_one_never_takes_a_bare_clear():
    """#159: ten SLC revs cleared the naming criterion with the bare
    word — the attention-forcing device (name the MAIN-claim entry +
    remaining distance) was bypassed by the output template, on the one
    criterion built to catch a main claim orbiting untouched.
    Mechanical: a bare clear there is malformed; other criteria keep
    bare clear."""
    n = adversary.NAMING_CRITERION
    bare = {k: "clear" for k in adversary.CRITERIA_KEYS}
    v, err = adversary.parse_verdict(json.dumps({"criteria": bare}))
    assert v is None and f"criterion {n}" in err and "naming" in err
    # Punctuation-only annotation is still bare.
    bare[n] = "clear: "
    v, err = adversary.parse_verdict(json.dumps({"criteria": bare}))
    assert v is None and f"criterion {n}" in err
    # A real naming passes.
    bare[n] = "clear: entry closing the main claim — two steps stand"
    v, err = adversary.parse_verdict(json.dumps({"criteria": bare}))
    assert err == "" and v["verdict"] == "pass"


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
                        "proof": f"Roadmap: the brick\n## Need\nbrick v{n}"}),
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
    # Next wake gets the one-line record, never the draft — and it says
    # the batch never dispatched (the plan note, persisted before the
    # judgment, claims otherwise; 07-29 SG ×2).
    assert row["discard_reason"] == "adversary rebuttal"
    notice = programme.rejection_notice(conn, "p")
    assert notice and "adversary rebuttal" in notice
    assert "Batch not dispatched" in notice
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


def test_mechanical_discard_also_records_a_reason(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The non-Adversary discard paths (package verify exhausted,
    revision spawn rc≠0, unusable revision output) left NO record
    anywhere pre-v34, while the plan note — persisted before the batch
    is judged — survived asserting the dispatch. Two SG wakes (07-29)
    burned reconstructing that. Every discarded proposal now records a
    row naming which channel dropped it."""
    _insert_root(conn)
    monkeypatch.setenv("ASTERISM_STRATEGIST_VERIFY_RETRY", "1")

    def fake_spawn(**kw):
        if kw.get("kind") == "adversary":  # pragma: no cover — never reached
            raise AssertionError("gate must reject before the judge")
        # A route-moving batch with no experiment: the package gate
        # rejects it mechanically, every round.
        (kw["attempts_dir"] / "decision.json").write_text(
            json.dumps({"kind": "EmitDirective",
                        "scope": "problem:p", "body": "hint",
                        "reason": "note"}), encoding="utf-8")
        (kw["attempts_dir"] / "proposal.md").write_text(
            _PROPOSAL, encoding="utf-8")
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=1,
        workspace=workspace, mfst=mfst, pipeline_id="adv-mech",
    )
    assert r.outcome == "failed"
    assert r.failure_reason == "strategist_schema_invalid"
    row = conn.execute(
        "SELECT * FROM programme_revisions WHERE problem='p'"
        " AND status='rejected'").fetchone()
    assert row is not None
    assert row["discard_reason"] == "package verify rejected"
    notice = programme.rejection_notice(conn, "p")
    assert notice and "package verify" in notice


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


def test_worker_section_pins_within_the_goals_own_group(
        workspace: Path, conn: sqlite3.Connection):
    """#164: revision chains are per group, each numbered from 1, so
    "has the Programme moved on?" must be asked of the goal's OWN
    chain. Live defect (SLC 08-04): goal 7309, authorised by sub-group
    370's only rev (1), was told the Programme had "moved on" to the
    TOP group's rev 27 — and pointed at the top group's PROGRAMME.md."""
    from Tooling.agent import context as wctx
    from Tooling.state import groups as groups_store

    top = groups_store.ensure_top_group(conn, "p")
    for n in range(3):
        programme.record_pass(conn, "p", _PROPOSAL, {"verdict": "pass"},
                              [], 0, f"top-b{n}", group_id=top)
    child = groups_store.open_group(conn, problem="p",
                                    parent_group_id=top,
                                    charter="settle the Hopf claim")
    programme.record_pass(
        conn, "p",
        _PROPOSAL.replace("The route holds.", "The child route holds."),
        {"verdict": "pass"}, [], 0, "child-b1", group_id=child)
    g = db.insert_goal(conn, problem="p", slug="child_brick",
                       lean_path="Problems/p/proofs/L_child_brick.lean",
                       statement="theorem child_brick : T",
                       origin="forward", depth=1, status="open")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, batch_id, group_id,"
        " produced_goal_id, created_at, updated_at)"
        " VALUES ('p', 0, 'inject_batch_done', 'Inject', 'child-b1', ?,"
        " ?, ?, ?)", (child, g, db.now(), db.now()))
    conn.commit()

    pdir = workspace / "Problems" / "p"
    w = "\n".join(wctx._section_programme_worker(conn, "p", None, pdir,
                                                 goal_id=g))
    # The child's chain is at rev 1 = the authorising rev: no false
    # "moved on" warning stamped with a sibling chain's rev number.
    assert "The child route holds." in w
    assert "moved on" not in w
    # The pointer names the child group's own render, and it resolves.
    assert f".groups/{child}/PROGRAMME.md" in w
    assert (pdir / ".groups" / str(child) / "PROGRAMME.md").exists()


def test_plan_note_provenance_is_group_scoped(
        workspace: Path, conn: sqlite3.Connection):
    """#164 class: the plan note is per group, so its provenance stamp
    must be too — a sub-group Strategist stamped with the TOP group's
    last batch + rev count would read every one of its own wakes as a
    phantom batch."""
    from Tooling.agent import phase2_context
    from Tooling.state import groups as groups_store

    top = groups_store.ensure_top_group(conn, "p")
    programme.record_pass(conn, "p", _PROPOSAL, {"verdict": "pass"},
                          [], 0, "top-b1", group_id=top)
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, batch_id, group_id, created_at,"
        " updated_at) VALUES ('p', 0, 'routine', 'Inject', 'top-b1', ?,"
        " ?, ?)", (top, db.now(), db.now()))
    child = groups_store.open_group(conn, problem="p",
                                    parent_group_id=top,
                                    charter="settle the sub-claim")
    conn.commit()

    line_top = phase2_context._plan_note_provenance(conn, "p", top)
    assert "top-b1" in line_top and "rev 1" in line_top
    # The fresh child has NO batches and NO revs of its own — its
    # provenance must say so, not echo the parent's history.
    line_child = phase2_context._plan_note_provenance(conn, "p", child)
    assert "no batch committed" in line_child
    assert "no Programme rev" in line_child


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


def test_projection_ships_standing_directive_even_when_unchanged(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Criterion 5 (`the directive must not contradict the Programme`)
    was unjudgeable on any batch that left the directive alone: only a
    batch-emitted body reached `decisions.md`, so the judge ruled on
    text it could not read and demoted a possibly-real mis-citation to
    a reservation (07-29 SG judge feedback). The directive in force
    ships every round, with the batch that emitted it."""
    attempts = workspace / ".attempts" / "adv-dir"
    attempts.mkdir(parents=True)
    pdir = workspace / "Problems" / "p"
    conn.execute(
        "UPDATE problems SET strategist_directive = ? WHERE name = 'p'",
        ("item 2: use `sq_pos_of_ne_zero`",))
    conn.execute(
        "INSERT INTO strategist_decisions"
        " (problem, triggered_at_tick, trigger_kind, decision_kind,"
        "  batch_id, created_at, updated_at)"
        " VALUES ('p', 1, 'routine', 'EmitDirective', 'batch-abc',"
        "         '2026-07-30T01:02:03Z', '2026-07-30T01:02:03Z')")
    conn.commit()

    proj = adversary.build_projection(
        round_no=1, attempts_dir=attempts, problem_dir=pdir,
        conn=conn, problem="p", proposal_body=_PROPOSAL,
        # this batch emits NO directive — the standing one still ships
        decisions=[_d("Inject", pipeline="Forward", brief="## Need\nx")],
        dialogue=[], proof_warn=None)

    text = (proj / "directive.md").read_text(encoding="utf-8")
    assert "sq_pos_of_ne_zero" in text
    assert "batch-abc" in text


def test_projection_directive_absent_says_so(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """No directive in force → the file still exists and says none, so
    the judge never has to distinguish "empty" from "not shipped"."""
    attempts = workspace / ".attempts" / "adv-dir0"
    attempts.mkdir(parents=True)
    proj = adversary.build_projection(
        round_no=1, attempts_dir=attempts,
        problem_dir=workspace / "Problems" / "p",
        conn=conn, problem="p", proposal_body=_PROPOSAL,
        decisions=[_d("Inject", pipeline="Forward", brief="## Need\nx")],
        dialogue=[], proof_warn=None)
    assert "(none" in (proj / "directive.md").read_text(encoding="utf-8")


def test_projection_does_not_stage_proofs(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Staging retired (user call 2026-08-04): the judge reads the
    problem's `proofs/` in place. The cited-file selection + cap-20
    systematically truncated the evidence late in a big problem (SLC:
    43 of 63 reachable files NOT staged at Ingest-adjacent rounds) —
    every curation rule was itself the defect, so no copies at all."""
    pdir = workspace / "Problems" / "p"
    (pdir / "proofs" / "L_cited.lean").write_text(
        "def cited : Prop := True\n", encoding="utf-8")
    attempts = workspace / ".attempts" / "adv-nostage"
    attempts.mkdir(parents=True)

    proj = adversary.build_projection(
        round_no=1, attempts_dir=attempts,
        problem_dir=pdir, conn=conn, problem="p",
        proposal_body=_PROPOSAL + "\nuses cited in the argument",
        decisions=[_d("Inject", pipeline="Forward",
                      brief="cite `cited`")],
        dialogue=[], proof_warn=None)

    assert not (proj / "proofs").exists()


def test_judge_reads_proofs_and_papers_in_place(
    workspace: Path, conn: sqlite3.Connection, monkeypatch,
) -> None:
    """The staging replacement: the spawn carries read-only grants on
    the REAL proofs dir and the paper shelf (`extra_read_dirs`) and the
    prompt's `{proofs_dir}` / `{papers_dir}` placeholders are
    substituted with the concrete paths — a judge told to decide
    RETARGETED and faithfulness-to-the-paper disputes "by these files"
    must be able to open every one of them, not a curated subset (the
    old SLC judge accepted a paper-grounded load-bearing claim on
    consistency with a prior judge's pointer because Papers/ sat
    outside its readable roots — rev 5 reservation, g368)."""
    from Tooling.pipeline import adversary as adv
    attempts = workspace / ".attempts" / "adv-inplace"
    attempts.mkdir(parents=True)
    pdir = workspace / "Problems" / "p"
    seen = {}

    def fake_spawn(**kw):
        seen.update(kw)
        (Path(kw["attempts_dir"]) / "verdict.json").write_text(
            _clear_criteria_json(),
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    verdict, err, rc = adv.review(
        round_no=1, attempts_dir=attempts, problem_dir=pdir, conn=conn,
        problem="p", proposal_body=_PROPOSAL, decisions=[], dialogue=[],
        proof_warn=None)
    assert rc == 0 and verdict is not None

    proofs_dir = (pdir / "proofs").resolve()
    papers_dir = (workspace / "Papers").resolve()
    assert seen["extra_read_dirs"] == (proofs_dir, papers_dir)
    rendered = Path(seen["prompt_path"]).read_text(encoding="utf-8")
    assert adv.PROOFS_DIR_PLACEHOLDER not in rendered
    assert adv.PAPERS_DIR_PLACEHOLDER not in rendered
    assert proofs_dir.as_posix() in rendered
    assert papers_dir.as_posix() in rendered


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


def test_projection_stages_tree_and_directive_body(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """07-29 judge feedback batch: TREE.md rides along; the directive
    BODY (payload['body'] on real Decisions — `.body` only ever existed
    on test fixtures) reaches decisions.md; goal targets are annotated
    (slug, status) since CATALOG carries names, not ids. (The staged
    proofs copies this test once covered were retired 2026-08-04 —
    the judge now reads proofs/ in place.)"""
    attempts = workspace / ".attempts" / "adv-stage"
    attempts.mkdir(parents=True)
    pdir = workspace / "Problems" / "p"
    (pdir / "TREE.md").write_text("# t\nmain  (frozen)\n", encoding="utf-8")
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
        proposal_body=_PROPOSAL,
        decisions=decisions, dialogue=[], proof_warn=None)
    assert (proj / "TREE.md").exists()
    dec = (proj / "decisions.md").read_text(encoding="utf-8")
    assert "DIRECTIVE BODY LINE" in dec
    assert f"→ {gid} (`tgt`, proved)" in dec


def _rendered_subgroup_section() -> str:
    """The conditional `## Your group` Context section as a sub-group
    actually receives it — the other half of the Strategist's contract
    since v35."""
    import sqlite3 as _sqlite3
    from Tooling.state import db as _db, groups as _groups
    from Tooling.agent import phase2_context as _ctx
    conn = _sqlite3.connect(":memory:")
    conn.row_factory = _sqlite3.Row
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Manifest.md', 't')")
    top = _groups.ensure_top_group(conn, "p")
    sub = _groups.open_group(conn, problem="p", parent_group_id=top,
                             charter="c")
    # `CloseGroup` lives in the parent-side conditional section, so the
    # guard renders that one too — from a group that HAS a child.
    return "\n".join(_ctx._section_your_group(conn, "p", sub)
                     + _ctx._section_groups_in_flight(conn, "p", top))


def test_the_two_antipatterns_are_one_text_in_four_files() -> None:
    """Both sides must name the same two failure modes in the same
    words — the author is told they wear the look of progress, the judge
    is told they fire criterion 1, and if those descriptions drift the
    judge rebuts on a shape the Strategist was told to write.

    The disease is the one `research_mission_design.md` opens with —
    "decently walking known ground forever" — and the union_closed
    entropy track is the live instance: its own Roadmap records a
    ceiling at ψ ≈ 0.382 while the requirement is 1/2, and batches kept
    formalizing under it. Only the lead line differs between the two
    sides; these two bullets do not.
    """
    root = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"
    files = [root / "adversary" / "adversary.md"] + [
        root / "strategist" / f for f in
        ("routine.md", "inject_batch_done.md", "pending_review.md")]
    for phrase in ("an expensive substitution",
                   "a problem circled is never solved",
                   "do not help settle the final problem",
                   "Plan the bricks in AHEAD and lay them"):
        for f in files:
            assert phrase in f.read_text(encoding="utf-8"), (
                f"{f.name} lost: {phrase!r}")


def test_adversary_contract_section_matches_wake_prompts() -> None:
    """07-29 (A): the judge carries a verbatim copy of the Strategist's
    decision-kind contract so quoted contract clauses are checkable
    inside the sandbox. Every bullet must exist byte-for-byte in one of
    the three wake prompts — editing a wake bullet without updating the
    judge's copy fails here.

    07-31: the copy moved out of the inlined prompt into `_contract.md`,
    staged into the projection. Reference material does not belong in an
    instruction that is re-sent on every spawn; the drift guard follows
    it.

    08-02 (v35): `ReturnToParent` is a sub-group-only verb, so its
    contract lives in the conditional `## Your group` Context section
    rather than the static prompt (a reader who cannot use a verb should
    not be shown it). The guard follows the text there too — the judge's
    copy must still match whatever the Strategist was actually told."""
    import re as _re
    import sqlite3 as _sqlite3
    root = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"
    section = (root / "adversary" / "_contract.md").read_text(
        encoding="utf-8")
    wakes = "".join(
        (root / "strategist" / f).read_text(encoding="utf-8")
        for f in ("routine.md", "inject_batch_done.md",
                  "pending_review.md"))
    wakes += _rendered_subgroup_section()
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

    # …and the REVERSE direction, which is what was missing (2026-08-11).
    # The guard above only asked "is every contract bullet real?" — never
    # "does the judge have every rule?" — so `Same-batch mints must be
    # independent` lived in all three wake prompts and in none of the
    # judge's, and 16 Injects across 4 batches broke it without one
    # rebuttal. One of them told g7491's worker to cite a brick minted in
    # its own batch; the worker could not find it (a mint has no goal row
    # until its Forward commits) and rebuilt it, spending a third of its
    # budget on a sibling's work.
    #
    # Anchored on the `## Rules` heading: framework-authored structure,
    # not agent prose, so this reads a section boundary rather than
    # detecting free text.
    rules = _re.search("\n## Rules\n(.*?)(?=\n## )", wakes, _re.S)
    assert rules, "the wake prompts lost their `## Rules` section"
    for line in rules.group(1).splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        assert line in section, (
            "a rule the Strategist is held to never reached the judge: "
            + line[:140])


def test_contract_standing_rules_are_real_wake_rules() -> None:
    """The guard above stops at the `target_goal_id` line, so it reads
    the decision-kind half of the judge's copy and nothing else. Below
    that sits `Standing rules the batch itself must satisfy — same
    source, same words`: the bullets the judge cites when it fires, and
    until 2026-08-14 no test compared any of them to anything.

    They were all still verbatim when this was written — but "correct
    today" is what an unguarded copy always looks like right up to the
    edit that splits it, and the judge quoting a clause the Strategist
    was never given is a rebuttal the Strategist cannot act on.

    The floor was 6 and is 4: the Roadmap's three time bands absorbed
    three bullets whose whole content was a band (2026-08-14). Lower it
    only alongside a deletion you meant — its job is to fail when the
    section moves and the parse silently finds nothing.
    """
    import re as _re
    root = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"
    section = (root / "adversary" / "_contract.md").read_text(
        encoding="utf-8")
    wakes = "".join(
        (root / "strategist" / f).read_text(encoding="utf-8")
        for f in ("routine.md", "inject_batch_done.md",
                  "pending_review.md"))
    # Bounded at both ends by framework-authored prose, not by counting:
    # the standing rules start after the `target_goal_id` note and end
    # at the `ReturnToParent` sentence, which is a group-verb remark
    # rather than a batch rule.
    tail = section.split("\n\n`target_goal_id`", 1)[1]
    tail = tail.split("\n\n`ReturnToParent`", 1)[0]
    bullets = [b.strip("\n") for b in _re.split(r"\n(?=- )", tail)
               if b.strip().startswith("- ")]
    assert len(bullets) >= 4, (
        f"only {len(bullets)} standing rules parsed — the section moved, "
        f"and a guard that parses nothing passes everything")
    for b in bullets:
        assert b in wakes, (
            "the judge holds the batch to a rule the Strategist was "
            "never given:\n" + b[:160])


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
        hits = [ln.lstrip("-0123456789. ") for ln in text.splitlines()
                if "**Rewrite `_plan.md`**" in ln]
        assert len(hits) == 1, (f, hits)
        steps.append(hits[0])
    assert len(set(steps)) == 1, steps
    assert "bare filename, in your attempts dir" in steps[0]


def test_proposal_section_shared_lines_synced() -> None:
    """07-29 programme readback: both SG and cube strategists misread
    'Carry ≥1' as a per-batch quota and paid a recurring defense
    paragraph in every revision; passed revisions also carried
    round-numbered concession narration. The corrective lines stay
    byte-identical across the three wake prompts."""
    root = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"
    texts = {
        f: (root / "strategist" / f).read_text(encoding="utf-8")
        for f in ("routine.md", "inject_batch_done.md",
                  "pending_review.md")}
    for needle in (
        "A batch must not leave your group idle: after it commits, "
        "something of yours is in flight, dispatched, or delivered.",
        "Every Inject is proven in the Proof — inject only what is "
        "fully argued",
    ):
        for f, t in texts.items():
            assert needle in t, (f, needle)


def test_review_retries_infra_rc_and_keeps_the_proposal(
    workspace: Path, conn: sqlite3.Connection, monkeypatch,
) -> None:
    """#132 (SG 07-30): one `adversary rc=1` provider blip made the whole
    strategist wake fail, discarding a finished proposal (28k tokens /
    6.2 min). An infra rc must cost a re-spawn, not the author's work;
    the verdict-problem budget stays separate."""
    from Tooling.pipeline import adversary
    monkeypatch.setattr(adversary, "INFRA_RETRY_BACKOFF_SEC", 0.0)
    attempts = workspace / ".attempts" / "pid"
    attempts.mkdir(parents=True, exist_ok=True)
    pdir = workspace / "Problems" / "p"
    calls = {"n": 0}

    def fake_spawn(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return 1                      # provider blip → spawn_fast_fail
        (Path(kw["attempts_dir"]) / "verdict.json").write_text(
            _clear_criteria_json(),
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    verdict, err, rc = adversary.review(
        round_no=1, attempts_dir=attempts, problem_dir=pdir, conn=conn,
        problem="p", proposal_body=_PROPOSAL, decisions=[], dialogue=[],
        proof_warn=None)
    assert calls["n"] == 2, "infra rc must be retried, not fatal"
    assert rc == 0 and err == "" and verdict is not None
    assert verdict["verdict"] == "pass"


def test_review_gives_up_after_the_infra_budget(
    workspace: Path, conn: sqlite3.Connection, monkeypatch,
) -> None:
    """A systematic provider failure still fails the wake — bounded, not
    an infinite re-spawn loop."""
    from Tooling.pipeline import adversary
    monkeypatch.setattr(adversary, "INFRA_RETRY_BACKOFF_SEC", 0.0)
    attempts = workspace / ".attempts" / "pid"
    attempts.mkdir(parents=True, exist_ok=True)
    pdir = workspace / "Problems" / "p"
    calls = {"n": 0}

    def always_infra(**kw):
        calls["n"] += 1
        return 1
    monkeypatch.setattr(agent, "spawn_llm", always_infra)
    verdict, err, rc = adversary.review(
        round_no=1, attempts_dir=attempts, problem_dir=pdir, conn=conn,
        problem="p", proposal_body=_PROPOSAL, decisions=[], dialogue=[],
        proof_warn=None)
    assert verdict is None and rc == 1
    assert calls["n"] == adversary.INFRA_SPAWN_RETRIES + 1


def test_review_verdict_budget_is_bounded(
    workspace: Path, conn: sqlite3.Connection, monkeypatch,
) -> None:
    """The no-verdict paths must count against VERDICT_TRIES — the infra
    branch turned the loop into `while True`, so an always-silent judge
    would otherwise spin forever."""
    from Tooling.pipeline import adversary
    attempts = workspace / ".attempts" / "pid"
    attempts.mkdir(parents=True, exist_ok=True)
    pdir = workspace / "Problems" / "p"
    calls = {"n": 0}

    def silent(**kw):
        calls["n"] += 1
        return 0                          # rc ok, but writes no verdict
    monkeypatch.setattr(agent, "spawn_llm", silent)
    verdict, err, rc = adversary.review(
        round_no=1, attempts_dir=attempts, problem_dir=pdir, conn=conn,
        problem="p", proposal_body=_PROPOSAL, decisions=[], dialogue=[],
        proof_warn=None)
    assert verdict is None and rc == 0 and "no verdict" in err
    assert calls["n"] == adversary.VERDICT_TRIES


def test_parse_verdict_tolerates_annotated_clear_and_fired() -> None:
    """07-29 third occurrence (2× b6_1 07-27, 1× SG): opus-tier judges
    annotate their verdicts — `"clear — I checked…"` — and the literal
    match discarded two full adversary rounds per hit, failing the
    whole wake as agent_no_output. Prefix-keyed with a word boundary:
    annotations tolerated, "clearly…" still malformed."""
    # The annotated form sits on the NAMING criterion (which requires an
    # annotation anyway) and the bare capitalised one on a criterion
    # that allows it — the subject here is annotation tolerance, not the
    # naming rule, and after the 2026-08-13 renumber those are different
    # numbers than they used to be.
    v, err = adversary.parse_verdict(json.dumps({"criteria": {
        "1": "Clear",
        "2": "clear — I checked the chain end to end",
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


def test_projection_ships_the_strategists_context_verbatim(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """A proposal may quote `Context.md`, and a citation the judge
    cannot open is a free pass (08-01 judge feedback): one round-1 fire
    on "you misquoted contract.md" came back in round 2 re-attributed to
    Context.md and had to be cleared unverified.

    VERBATIM, not selected sections — a filtered copy lets the judge
    fire on a line that exists but was withheld, which is the same
    defect wearing framework colours, and a section allowlist rots the
    first time someone adds a section. The Strategist's private plan
    note rides along by design (user ruling 08-01): it is lazily
    available, and a judge that sees "this route already died" in the
    plan note while the proposal re-proposes it is a judge doing its
    job."""
    attempts = workspace / ".attempts" / "adv-ctx"
    attempts.mkdir(parents=True)
    pdir = workspace / "Problems" / "p"
    body = ("## Framework stalled\n\nChoose one of: `Inject(...)`\n\n"
            "## Your plan note (private, cross-wake)\n\nFacts: x died.\n")
    (attempts / "Context.md").write_text(body, encoding="utf-8")

    proj = adversary.build_projection(
        round_no=1, attempts_dir=attempts, problem_dir=pdir,
        conn=conn, problem="p", proposal_body=_PROPOSAL,
        decisions=[_d("Inject", pipeline="Forward", brief="## Need\nx")],
        dialogue=[], proof_warn=None)

    shipped = (proj / "Context.md").read_text(encoding="utf-8")
    # The author's text rides CONTIGUOUS and complete — nothing filtered,
    # nothing rewritten, so every quotation stays checkable.
    assert shipped.endswith(body)
    # Above it, a framework label naming what this file is (2026-08-07):
    # a snapshot frozen at spawn. The judge fired criterion 5 on that
    # gap 5× in one run and said so in its own feedback; same move as
    # the PROGRAMME weld label.
    #
    # This used to also assert "live files are authoritative", which is
    # how a wrong sentence became a contract: `TREE.md` in the
    # projection is a COPY taken at round start, so the label was
    # ranking the STALER render above the record and the test was
    # holding it there (2026-08-15). What the label owes the judge is
    # the age of each file and a pointer to the thing that is actually
    # live; `test_no_false_liveness_claims.py` pins that.
    label = shipped[:-len(body)]
    assert "Framework label" in label
    assert "SNAPSHOT" in label
    assert "live files are authoritative" not in label


def test_projection_without_a_context_file_is_not_an_error(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Nothing in the package depends on it existing — a wake whose
    Context was never written must still get a projection."""
    attempts = workspace / ".attempts" / "adv-noctx"
    attempts.mkdir(parents=True)
    proj = adversary.build_projection(
        round_no=1, attempts_dir=attempts,
        problem_dir=workspace / "Problems" / "p",
        conn=conn, problem="p", proposal_body=_PROPOSAL,
        decisions=[_d("Inject", pipeline="Forward", brief="## Need\nx")],
        dialogue=[], proof_warn=None)
    assert not (proj / "Context.md").exists()
    assert (proj / "proposal.md").exists()


# ── the snapshot's embedded Programme: identity-gated elision ───────
# (owner condition 2026-08-15: elide ONLY what is byte-recoverable)


_LONG_REV = _PROPOSAL + ("The census argument, spelled out.\n" * 10).strip()


def _ctx_projection(workspace, conn, attempts_name, ctx_body):
    attempts = workspace / ".attempts" / attempts_name
    attempts.mkdir(parents=True)
    (attempts / "Context.md").write_text(ctx_body, encoding="utf-8")
    return adversary.build_projection(
        round_no=1, attempts_dir=attempts,
        problem_dir=workspace / "Problems" / "p",
        conn=conn, problem="p", proposal_body=_PROPOSAL,
        decisions=[_d("Inject", pipeline="Forward", brief="## Need\nx")],
        dialogue=[], proof_warn=None)


def test_snapshot_programme_identical_to_shipped_rev_is_elided(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """The adversary's grounding sweep paid the same 20-26KB twice per
    round: the snapshot embeds the Programme revision and PROGRAMME.md
    in the same projection opens with it. Byte-identical ⇒ a pointer
    that names where the identical text is; every elided byte stays
    recoverable verbatim."""
    programme.record_pass(conn, "p", _LONG_REV, {"verdict": "pass"},
                          [], 1, "b1")
    proj = _ctx_projection(
        workspace, conn, "adv-elide",
        "# Strategist context\n## Programme (rev 1)\n"
        + _LONG_REV + "\n## Alive goals\nmain\n")
    ctx = (proj / "Context.md").read_text(encoding="utf-8")
    assert "Programme revision text elided" in ctx
    assert "PROGRAMME.md" in ctx, "the pointer names where the text is"
    assert "spelled out" not in ctx
    assert "## Alive goals" in ctx, "only the identical span is elided"
    # …and the named file really carries the elided bytes
    assert _LONG_REV in (proj / "PROGRAMME.md").read_text(
        encoding="utf-8")


def test_snapshot_that_differs_at_all_ships_whole(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Any difference — a drifted snapshot, an older rev — and "what
    the author saw" must survive verbatim: it is not byte-recoverable
    from PROGRAMME.md, so nothing may be elided."""
    programme.record_pass(conn, "p", _LONG_REV, {"verdict": "pass"},
                          [], 1, "b1")
    drifted = _LONG_REV.replace("The route holds.", "The route held.")
    proj = _ctx_projection(
        workspace, conn, "adv-noelide",
        "# Strategist context\n## Programme (rev 1)\n" + drifted)
    ctx = (proj / "Context.md").read_text(encoding="utf-8")
    assert "Programme revision text elided" not in ctx
    assert "The route held." in ctx


def test_no_current_rev_leaves_the_snapshot_untouched(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    proj = _ctx_projection(workspace, conn, "adv-norev",
                           "# Strategist context\nno programme yet\n")
    ctx = (proj / "Context.md").read_text(encoding="utf-8")
    assert "no programme yet" in ctx
    assert "Programme revision text elided" not in ctx
