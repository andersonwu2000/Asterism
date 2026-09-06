"""Named bricks and `Uses:` (owner ruling 2026-09-07).

An `Inject` no longer carries a hand copy of its brick — it NAMES one,
and the name is the node's name: a mint lands as `proofs/L_<name>.lean`
with `theorem <name>`, a target-mode brick is named exactly as the
target goal's slug. What the copy used to buy (a per-brick argument the
worker can read) the `bricks` table buys instead, pinned to the revision
the judge passed.

`Uses:` is the second half. A brick another brick's argument consumes is
NOT injected: it reaches whichever worker declares a sub-goal of that
name, at any depth. That replaces the old workaround — "same-batch
Injects must be independent, so a lemma waits a batch".

The layers, in order: parse (`programme.parse_bricks`), verify
(`strategist.verify_injects` + the per-decision gate), the worker's
Context, the mint commit gate, the delivery report, and the judge's
`decisions.md`.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db, groups, programme
from Tooling.state import intent as intent_mod


PROOF = """### toggle_bijection
Theorem. The toggle map is a bijection.
Proof. It is an involution.

### even_sum_card
Uses: toggle_bijection
Theorem. The even-sum subsets number 2 ^ (n - 1).
Proof. Halve the powerset by `toggle_bijection`.
"""


def _body(proof: str = PROOF) -> str:
    return ("# A batch\n## Argument\nWhy this batch.\n"
            "## Proof\n" + proof + "\n## Roadmap\n1. the assembly\n")


# ─── A. parse_bricks ─────────────────────────────────────────────────

def test_parse_bricks_splits_named_bricks_with_their_uses():
    bricks, err = programme.parse_bricks(PROOF)
    assert err == ""
    assert [b.name for b in bricks] == ["toggle_bijection", "even_sum_card"]
    assert bricks[0].uses == ()
    assert bricks[1].uses == ("toggle_bijection",)
    assert bricks[1].head == "Theorem"
    assert bricks[1].statement.startswith("The even-sum subsets")
    assert bricks[1].argument.startswith("Halve the powerset")


def test_no_new_mathematics_is_zero_bricks_not_a_defect():
    assert programme.parse_bricks("No new mathematics this batch.") == ([], "")


def test_parse_bricks_refuses_a_body_with_no_header():
    _b, err = programme.parse_bricks("Theorem. x.\nProof. y.")
    assert "### <name>" in err


def test_parse_bricks_refuses_prose_before_the_first_header():
    _b, err = programme.parse_bricks(
        "Some framing prose.\n\n### a\nTheorem. x.\nProof. y.")
    assert "before the first" in err and "### <name>" in err


def test_parse_bricks_refuses_a_name_that_is_not_a_slug():
    for bad in ("Bad-Name", "9lives", "hasSpace name"):
        _b, err = programme.parse_bricks(
            f"### {bad}\nTheorem. x.\nProof. y.")
        assert "not a legal name" in err, bad


def test_parse_bricks_refuses_a_duplicate_name():
    _b, err = programme.parse_bricks(
        "### a\nTheorem. x.\nProof. y.\n\n### a\nTheorem. z.\nProof. w.")
    assert "duplicate brick name `a`" in err


def test_parse_bricks_refuses_a_uses_cycle():
    _b, err = programme.parse_bricks(
        "### a\nUses: b\nTheorem. x.\nProof. y.\n\n"
        "### b\nUses: a\nTheorem. z.\nProof. w.")
    assert "cycle" in err and "`a`" in err and "`b`" in err


def test_parse_bricks_refuses_a_self_use():
    _b, err = programme.parse_bricks(
        "### a\nUses: a\nTheorem. x.\nProof. y.")
    assert "cycle" in err


def test_parse_bricks_refuses_an_empty_uses_line():
    _b, err = programme.parse_bricks(
        "### a\nUses:\nTheorem. x.\nProof. y.")
    assert "empty `Uses:`" in err


def test_parse_bricks_carries_the_body_defect_with_the_name():
    _b, err = programme.parse_bricks("### a\nJust prose, no theorem.")
    assert err.startswith("brick `a`:") and "`Theorem.`" in err


def test_a_uses_name_outside_this_proof_is_verifys_question_not_parses():
    """Parse is text-level: whether `helper` is a node of the problem or
    a brick of another batch needs the record, which the parser has no
    business reaching for."""
    bricks, err = programme.parse_bricks(
        "### a\nUses: helper\nTheorem. x.\nProof. y.")
    assert err == "" and bricks[0].uses == ("helper",)


def test_uses_closure_is_transitive_within_the_revision():
    bricks, _ = programme.parse_bricks(
        "### a\nUses: b\nTheorem. x.\nProof. y.\n\n"
        "### b\nUses: c\nTheorem. z.\nProof. w.\n\n"
        "### c\nTheorem. q.\nProof. r.")
    assert programme.uses_closure(bricks, "a") == ["b", "c"]
    assert programme.uses_closure(bricks, "c") == []


# ─── B. the store ────────────────────────────────────────────────────

def _fresh(tmp_path: Path) -> "tuple[sqlite3.Connection, int]":
    c = db.connect(tmp_path / "t.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p', ?, 1)", (db.now(),))
    top = groups.ensure_top_group(c, "p")
    c.commit()
    return c, top


def test_a_passed_revision_records_its_bricks_by_name(tmp_path):
    conn, top = _fresh(tmp_path)
    programme.record_pass(conn, "p", _body(), {}, [], 0, "b1", group_id=top)
    rows = list(conn.execute(
        "SELECT name, uses_json FROM bricks WHERE problem='p' ORDER BY id"))
    assert [r["name"] for r in rows] == ["toggle_bijection", "even_sum_card"]
    assert json.loads(rows[1]["uses_json"]) == ["toggle_bijection"]
    b = programme.brick_by_name(conn, "p", "even_sum_card")
    assert b is not None and b.uses == ("toggle_bijection",)


def test_a_body_that_no_longer_parses_stores_nothing_and_still_passes(tmp_path):
    """Best-effort: the judge already ruled, and a revision recorded
    from a replay or a hand repair must not be refused at write time."""
    conn, top = _fresh(tmp_path)
    rev = programme.record_pass(
        conn, "p", _body("Unheaded prose."), {}, [], 0, "b1", group_id=top)
    assert rev == 1
    assert conn.execute("SELECT COUNT(*) FROM bricks").fetchone()[0] == 0


# ─── C. verify ───────────────────────────────────────────────────────

def _S():
    from Tooling.pipeline import strategist as s
    return s


def _inject(name, target=None):
    from Tooling.pipeline.strategist import Decision
    return Decision(kind="Inject", target_id=target,
                    payload={"brick": name})


def test_c1_an_inject_naming_no_brick_of_this_proof_is_refused(tmp_path):
    conn, _top = _fresh(tmp_path)
    S = _S()
    bricks, _ = programme.parse_bricks(PROOF)
    err = S.verify_injects([_inject("nowhere")], bricks, conn, problem="p")
    assert "`nowhere` is not a brick" in err
    assert "`toggle_bijection`" in err and "`even_sum_card`" in err


def test_c2_a_used_brick_is_not_injected(tmp_path):
    conn, _top = _fresh(tmp_path)
    S = _S()
    bricks, _ = programme.parse_bricks(PROOF)
    err = S.verify_injects([_inject("toggle_bijection")], bricks, conn,
                           problem="p")
    assert "is used by `even_sum_card`" in err
    assert "declares a sub-goal named `toggle_bijection`" in err
    assert "Inject `even_sum_card` instead" in err
    # …and the consumer itself is fine.
    assert S.verify_injects([_inject("even_sum_card")], bricks, conn,
                            problem="p") == ""


def test_c3_a_mint_name_already_taken_is_refused_before_the_worker_spends(
        tmp_path):
    conn, top = _fresh(tmp_path)
    S = _S()
    gid = db.insert_goal(conn, problem="p", slug="even_sum_card",
                         lean_path="Problems/p/proofs/L_even_sum_card.lean",
                         statement="T", origin="forward")
    db.update_goal_status(conn, gid, "proved")
    err = S.verify_decision(_inject("even_sum_card"), conn, problem="p",
                            group_id=top)
    assert f"taken by g{gid} (proved)" in err
    assert "Target it" in err and "pick another name" in err


def test_c3_a_landed_proof_file_of_that_name_is_refused(tmp_path, monkeypatch):
    conn, top = _fresh(tmp_path)
    S = _S()
    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / "L_even_sum_card.lean").write_text("x", encoding="utf-8")
    err = S.verify_decision(_inject("even_sum_card"), conn, problem="p",
                            group_id=top, workspace=tmp_path)
    assert "L_even_sum_card.lean` already exists" in err


def test_c4_a_target_mode_brick_must_carry_the_goals_slug(tmp_path):
    conn, top = _fresh(tmp_path)
    S = _S()
    gid = db.insert_goal(conn, problem="p", slug="main",
                         lean_path="Problems/p/Root.lean", statement="T",
                         origin="root", depth=0)
    err = S.verify_decision(_inject("something_else", target=gid), conn,
                            problem="p", group_id=top)
    assert f"the brick for g{gid} must be named `main`" in err
    assert S.verify_decision(_inject("main", target=gid), conn, problem="p",
                             group_id=top) == ""


def test_c5_a_uses_name_with_nothing_behind_it_is_refused(tmp_path):
    conn, _top = _fresh(tmp_path)
    S = _S()
    bricks, _ = programme.parse_bricks(
        "### a\nUses: ghost\nTheorem. x.\nProof. y.")
    err = S.verify_injects([_inject("a")], bricks, conn, problem="p")
    assert "`ghost`" in err and "nor a node of this problem" in err


def test_c5_a_uses_name_resolving_to_a_parked_goal_names_its_status(tmp_path):
    conn, _top = _fresh(tmp_path)
    S = _S()
    gid = db.insert_goal(conn, problem="p", slug="ghost",
                         lean_path="Problems/p/proofs/L_ghost.lean",
                         statement="T", origin="forward")
    db.update_goal_status(conn, gid, "shelved")
    bricks, _ = programme.parse_bricks(
        "### a\nUses: ghost\nTheorem. x.\nProof. y.")
    err = S.verify_injects([_inject("a")], bricks, conn, problem="p")
    assert f"g{gid} `ghost` is shelved" in err
    # An alive or proved node is a legitimate citation.
    db.update_goal_status(conn, gid, "open")
    assert S.verify_injects([_inject("a")], bricks, conn, problem="p") == ""


def test_c6_a_decision_that_still_carries_proof_is_refused(tmp_path):
    conn, top = _fresh(tmp_path)
    S = _S()
    d = S.Decision(kind="Inject", brief="Theorem. x.\nProof. y.")
    err = S.verify_decision(d, conn, problem="p", group_id=top)
    assert "no longer carries `proof`" in err
    assert '"brick"' in err and "### <name>" in err


def test_the_slug_not_found_message_names_uses_as_the_way_out(tmp_path):
    """2026-08-22's message told the author to fold the dependent step
    into the mint's own proof. `Uses:` is that step's home now."""
    conn, top = _fresh(tmp_path)
    S = _S()
    d = S.Decision(kind="Inject", target_id="not_yet",
                   payload={"brick": "not_yet"})
    err = S.verify_decision(d, conn, problem="p", group_id=top)
    assert "Uses: not_yet" in err
    assert "fold the dependent step" not in err


# ─── D. worker Context ───────────────────────────────────────────────

def _seed_batch(tmp_path, *, proof: str = PROOF, brick: str = "even_sum_card",
                target=None):
    """A problem with one passed revision and one Inject naming `brick`.
    Returns (conn, top, decision_id)."""
    conn, top = _fresh(tmp_path)
    ts = db.now()
    did = int(conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, brick_name,"
        " batch_id, payload, created_at, updated_at)"
        " VALUES ('p', 1, 'inject_batch_done', 'Inject', ?, ?, ?, 'b1',"
        " '{}', ?, ?)", (top, target, brick, ts, ts)).lastrowid)
    programme.record_pass(conn, "p", _body(proof), {}, [], 0, "b1",
                          group_id=top)
    conn.commit()
    return conn, top, did


def test_the_argument_renders_as_the_named_brick(tmp_path):
    from Tooling.agent import context as ctx
    conn, _top, did = _seed_batch(tmp_path)
    text = "\n".join(ctx._section_strategist_brief(conn, did))
    assert "## The argument for this brick" in text
    assert "### even_sum_card" in text
    assert "Uses: toggle_bijection" in text
    assert "Theorem. The even-sum subsets number 2 ^ (n - 1)." in text
    assert "Proof. Halve the powerset" in text


def test_a_legacy_row_keeps_todays_rendering(tmp_path):
    from Tooling.agent import context as ctx
    conn, top = _fresh(tmp_path)
    ts = db.now()
    did = int(conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, brief, payload,"
        " created_at, updated_at)"
        " VALUES ('p', 1, 'routine', 'Inject', ?, ?, '{}', ?, ?)",
        (top, "Theorem. legacy.\nProof. copied by hand.", ts,
         ts)).lastrowid)
    conn.commit()
    text = "\n".join(ctx._section_strategist_brief(conn, did))
    assert "Theorem. legacy." in text and "### " not in text


def test_a_subgoal_finds_its_brick_by_slug_with_no_decision(tmp_path):
    """The `Uses:` channel: nothing dispatched `toggle_bijection`, and
    the worker that declares a sub-goal of that name gets its argument
    anyway."""
    from Tooling.agent import context as ctx
    conn, _top, _did = _seed_batch(tmp_path)
    gid = db.insert_goal(conn, problem="p", slug="toggle_bijection",
                         lean_path="Problems/p/proofs/L_toggle_bijection.lean",
                         statement="T", origin="backward", depth=1)
    text = "\n".join(ctx._section_strategist_brief(
        conn, None, gid, problem="p", slug="toggle_bijection"))
    assert "### toggle_bijection" in text
    assert "Theorem. The toggle map is a bijection." in text


def test_the_named_lemmas_section_carries_the_three_status_lines(tmp_path):
    from Tooling.agent import context as ctx
    conn, _top, did = _seed_batch(tmp_path)

    def _render():
        return "\n".join(ctx._section_named_lemmas(conn, "p", did))

    text = _render()
    assert "## Lemmas named by the strategist" in text
    assert "### toggle_bijection" in text
    assert "no node yet — declare a sub-goal `toggle_bijection`" in text
    assert "Theorem. The toggle map is a bijection." in text
    assert "Proof. It is an involution." in text

    gid = db.insert_goal(conn, problem="p", slug="toggle_bijection",
                         lean_path="Problems/p/proofs/L_toggle_bijection.lean",
                         statement="T", origin="backward", depth=1)
    assert f"alive: g{gid} (open) — cite it" in _render()
    db.update_goal_status(conn, gid, "proved")
    assert f"landed: g{gid} — cite it" in _render()


def test_a_brick_with_no_uses_renders_no_lemmas_section(tmp_path):
    from Tooling.agent import context as ctx
    conn, _top, did = _seed_batch(tmp_path, brick="toggle_bijection")
    assert ctx._section_named_lemmas(conn, "p", did) == []


def test_the_mint_worker_reads_the_lemmas_section_too(tmp_path, monkeypatch):
    from Tooling.agent.phase2_context.forward import compile_forward_context
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Problems" / "p" / "proofs").mkdir(parents=True)
    conn, _top, did = _seed_batch(tmp_path)
    attempts = tmp_path / ".attempts" / "pid-1"
    attempts.mkdir(parents=True)
    compile_forward_context(
        conn, problem="p", decision_id=did, attempts_dir=attempts,
        workspace=tmp_path,
        intent=intent_mod.ProblemIntent(problem="p", charter="T"))
    text = (attempts / "Context.md").read_text(encoding="utf-8")
    assert "## Lemmas named by the strategist" in text
    assert "### toggle_bijection" in text


# ─── E. the mint commit gate ─────────────────────────────────────────

def test_the_mint_head_must_carry_the_bricks_name(tmp_path):
    from Tooling.pipeline import forward
    conn, _top, did = _seed_batch(tmp_path)
    assert forward._decision_brick_name(conn, did) == "even_sum_card"
    # No decision, or a legacy row that named nothing: the gate is silent.
    assert forward._decision_brick_name(conn, None) == ""


def test_a_mint_under_the_wrong_name_is_rejected_with_the_required_one():
    from Tooling.pipeline import forward
    meta, err = forward.extract_forward_metadata(
        "import Mathlib\nnamespace Problems.p\n"
        "theorem wrong_name : True := by trivial\nend Problems.p\n")
    assert meta is not None and err == ""
    defect = forward.brick_name_defect("even_sum_card", meta)
    assert "`theorem wrong_name`" in defect
    assert "named `even_sum_card`" in defect
    assert "Rename the declaration head to `theorem even_sum_card`" in defect
    # The right name passes, and an unnamed brick holds the worker to
    # nothing (a BFS-auto-dispatch, a legacy row, a human Inject).
    right, _ = forward.extract_forward_metadata(
        "import Mathlib\nnamespace Problems.p\n"
        "theorem even_sum_card : True := by trivial\nend Problems.p\n")
    assert forward.brick_name_defect("even_sum_card", right) == ""
    assert forward.brick_name_defect("", meta) == ""


# ─── F. the delivery report ──────────────────────────────────────────

def _settle(conn, did, *, outcome="success", produced=None):
    conn.execute(
        "UPDATE strategist_decisions SET outcome = ?, produced_goal_id = ?,"
        " updated_at = ? WHERE id = ?",
        (outcome, produced, db.now(), did))
    conn.commit()


def _report(conn, top):
    from Tooling.agent import phase2_context
    return "\n".join(phase2_context._section_inject_batch_outcomes(
        conn, "p", group_id=top))


def test_the_report_names_every_brick_of_the_batch(tmp_path):
    conn, top, did = _seed_batch(tmp_path)
    gid = db.insert_goal(conn, problem="p", slug="even_sum_card",
                         lean_path="Problems/p/proofs/L_even_sum_card.lean",
                         statement="T", origin="forward", depth=1)
    db.update_goal_status(conn, gid, "proved")
    _settle(conn, did, produced=gid)
    text = _report(conn, top)
    assert "Bricks this batch named" in text
    assert f"`even_sum_card`: dispatched → landed g{gid}" in text
    # The used brick's subtree settled and nobody declared it.
    assert ("`toggle_bijection`: unused — `even_sum_card`'s subtree "
            "settled with no node named `toggle_bijection`") in text


def test_the_report_says_a_used_brick_appeared_as_a_subgoal(tmp_path):
    conn, top, did = _seed_batch(tmp_path)
    parent = db.insert_goal(
        conn, problem="p", slug="even_sum_card",
        lean_path="Problems/p/proofs/L_even_sum_card.lean",
        statement="T", origin="forward", depth=1)
    _settle(conn, did, produced=parent)
    kid = db.insert_goal(
        conn, problem="p", slug="toggle_bijection",
        lean_path="Problems/p/proofs/L_toggle_bijection.lean",
        statement="T", origin="backward", depth=2)
    sid = int(conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, status,"
        " proposal_md, created_by, created_at) VALUES (?,'','','proposed',"
        " '', 'test', ?)", (parent, db.now())).lastrowid)
    conn.execute("INSERT INTO strategy_subgoals (strategy_id, subgoal_id,"
                 " position) VALUES (?, ?, 0)", (sid, kid))
    db.update_goal_status(conn, parent, "proved")
    db.update_goal_status(conn, kid, "proved")
    conn.commit()
    text = _report(conn, top)
    assert (f"`toggle_bijection`: appeared as sub-goal g{kid} "
            f"under g{parent}") in text


def test_the_report_calls_a_pre_existing_node_cited(tmp_path):
    conn, top, did = _seed_batch(tmp_path)
    old = db.insert_goal(
        conn, problem="p", slug="toggle_bijection",
        lean_path="Problems/p/proofs/L_toggle_bijection.lean",
        statement="T", origin="forward", depth=1)
    conn.execute("UPDATE goals SET created_at = '2000-01-01T00:00:00+00:00'"
                 " WHERE id = ?", (old,))
    gid = db.insert_goal(conn, problem="p", slug="even_sum_card",
                         lean_path="Problems/p/proofs/L_even_sum_card.lean",
                         statement="T", origin="forward", depth=1)
    db.update_goal_status(conn, gid, "proved")
    _settle(conn, did, produced=gid)
    assert f"`toggle_bijection`: pre-existing g{old}, cited" in _report(
        conn, top)


def test_the_report_says_pending_while_the_subtree_is_in_flight(tmp_path):
    conn, top, did = _seed_batch(tmp_path)
    parent = db.insert_goal(
        conn, problem="p", slug="even_sum_card",
        lean_path="Problems/p/proofs/L_even_sum_card.lean",
        statement="T", origin="forward", depth=1)
    _settle(conn, did, produced=parent)
    kid = db.insert_goal(
        conn, problem="p", slug="other_step",
        lean_path="Problems/p/proofs/L_other_step.lean",
        statement="T", origin="backward", depth=2)
    sid = int(conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, status,"
        " proposal_md, created_by, created_at) VALUES (?,'','','proposed',"
        " '', 'test', ?)", (parent, db.now())).lastrowid)
    conn.execute("INSERT INTO strategy_subgoals (strategy_id, subgoal_id,"
                 " position) VALUES (?, ?, 0)", (sid, kid))
    conn.commit()
    assert ("`toggle_bijection`: pending — `even_sum_card`'s subtree "
            "in flight") in _report(conn, top)


# ─── G. the judge's decisions.md ─────────────────────────────────────

def test_decisions_md_renders_the_name_and_never_a_proof_body():
    from Tooling.pipeline import adversary
    from Tooling.pipeline.strategist import Decision
    text = adversary._decisions_digest([
        Decision(kind="Inject", payload={"brick": "even_sum_card"}),
        Decision(kind="Inject", target_id=7,
                 payload={"brick": "main"}, reason="the root"),
    ])
    assert "## 1. Inject brick=even_sum_card" in text
    assert "## 2. Inject brick=main → 7" in text
    assert "proof" not in text.lower()


def test_decisions_md_does_not_echo_a_legacy_proof_body():
    """The ruling is unconditional: the argument is read in the
    `## Proof`, once. A legacy row's prose is not a second copy the
    judge should be handed."""
    from Tooling.pipeline import adversary
    from Tooling.pipeline.strategist import Decision
    text = adversary._decisions_digest(
        [Decision(kind="Inject", brief="Theorem. LEAKED.\nProof. x.")])
    assert "LEAKED" not in text


def test_the_batch_judges_rubric_has_four_criteria():
    from Tooling.pipeline import adversary
    assert adversary.CRITERIA_KEYS == ("1", "2", "3", "4")
    v, err = adversary.parse_verdict(json.dumps({"criteria": {
        "1": ["clear: the chain reaches the charter"],
        "2": ["clear: the Relation is argued"],
        "3": ["clear: every PAST line cites"],
        "4": ["clear: the Proof is complete"]}}))
    assert err == "" and v is not None and v["verdict"] == "pass"


@pytest.mark.parametrize("path", [
    "Tooling/prompts/adversary/adversary.md",
    "Tooling/prompts/adversary/_contract.md",
])
def test_no_residue_of_criterion_five_in_the_batch_judge_path(path):
    root = Path(__file__).resolve().parents[1]
    text = (root / path).read_text(encoding="utf-8")
    assert "5." not in text.replace("2026-09-05.", "")
    assert '"5"' not in text
