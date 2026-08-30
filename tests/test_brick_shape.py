"""The two-part brick (owner ruling 2026-08-30).

Every brick a batch dispatches is written the way a mathematician
writes it — `Theorem.` its full statement, then `Proof.` its argument
— and the Inject's `proof` carries exactly that. The statement thereby
gets a structural position of its own: the mint worker's
`## Your assignment` (p406, 2026-08-30: with the claim buried in prose
the intake measured a lemma brick against the charter's root and
bounced it back to the Strategist), a per-brick unit for the judge, a
handle for dedupe and for same-gap detection across revisions. A
definition brick writes `Definition.` and carries no `Proof.`.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db, groups, programme
from Tooling.state import intent as intent_mod


BRICK = ("Theorem. For every n, f n ≤ n.\n\n"
         "Proof. Induction on n; the step uses the monotone bound.\n")
BOLD = ("**Theorem.** For every n, f n ≤ n.\n\n"
        "**Proof.** Induction on n.\n")
DEF = ("Definition. `w F` is the number of members of `F` containing "
       "the point of largest degree.\n")
PROSE = "Prove simultaneously that f n ≤ n; this follows by induction.\n"


# ─── the parser ──────────────────────────────────────────────────────

def test_parse_splits_statement_from_argument():
    head, stmt, arg, err = programme.parse_brick_proof(BRICK)
    assert (head, err) == ("Theorem", "")
    assert stmt == "For every n, f n ≤ n."
    assert arg.startswith("Induction on n")


def test_parse_accepts_bold_markers():
    head, stmt, arg, err = programme.parse_brick_proof(BOLD)
    assert (head, stmt, err) == ("Theorem", "For every n, f n ≤ n.", "")
    assert arg == "Induction on n."


def test_parse_definition_brick_needs_no_proof():
    head, stmt, arg, err = programme.parse_brick_proof(DEF)
    assert (head, err) == ("Definition", "")
    assert stmt.startswith("`w F` is") and arg == ""


def test_parse_names_the_defect():
    _, _, _, err = programme.parse_brick_proof(PROSE)
    assert "`Theorem.`" in err and "`Proof.`" in err
    _, _, _, err = programme.parse_brick_proof(
        "Proof. by induction.\nTheorem. f n ≤ n.\n")
    assert "before" in err
    _, _, _, err = programme.parse_brick_proof("Theorem. f n ≤ n.\n")
    assert "`Proof.`" in err


# ─── the verify gate ─────────────────────────────────────────────────

def _conn(tmp_path: Path) -> tuple[sqlite3.Connection, int]:
    c = db.connect(tmp_path / "asterism.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at) VALUES ('Test.bs', 't')")
    top = groups.ensure_top_group(c, "Test.bs")
    c.commit()
    return c, top


def _S():
    from Tooling.pipeline import strategist as s
    return s


def test_verify_rejects_an_inject_without_the_two_parts(tmp_path):
    conn, top = _conn(tmp_path)
    S = _S()
    err = S.verify_decision(S.Decision(kind="Inject", brief=PROSE), conn,
                            problem="Test.bs", group_id=top)
    assert "`Theorem.`" in err and "`Proof.`" in err


def test_verify_accepts_the_shape(tmp_path):
    conn, top = _conn(tmp_path)
    S = _S()
    for brief in (BRICK, BOLD, DEF):
        assert S.verify_decision(S.Decision(kind="Inject", brief=brief), conn,
                                 problem="Test.bs", group_id=top) == "", brief


# ─── the mint worker's assignment ────────────────────────────────────

def test_mint_worker_gets_the_statement_as_its_assignment(tmp_path, monkeypatch):
    from Tooling.agent.phase2_context.forward import compile_forward_context
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Problems" / "p" / "proofs").mkdir(parents=True)
    c = db.connect(tmp_path / "asterism.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p', ?, 1)", (db.now(),))
    groups.ensure_top_group(c, "p")
    ts = db.now()
    did = int(c.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, created_at, updated_at)"
        " VALUES ('p', 1, 'routine', 'Inject', ?, '{}', ?, ?)",
        (BRICK, ts, ts)).lastrowid)
    c.commit()
    attempts = tmp_path / ".attempts" / "pid-1"
    attempts.mkdir(parents=True)
    compile_forward_context(c, problem="p", decision_id=did,
                            attempts_dir=attempts, workspace=tmp_path,
                            intent=intent_mod.ProblemIntent(problem="p", charter="T"))
    text = (attempts / "Context.md").read_text(encoding="utf-8")
    i_asg = text.index("## Your assignment")
    i_arg = text.index("## The argument for this brick")
    assert i_asg < i_arg, "the statement comes first — it is what the worker mints"
    assert "For every n, f n ≤ n." in text[i_asg:i_arg]


# ─── the prompts name the shape ──────────────────────────────────────

_PROMPTS = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"


def test_strategist_prompts_ask_for_the_two_part_brick():
    for name in ("inject_batch_done.md", "pending_review.md"):
        text = (_PROMPTS / "strategist" / name).read_text(encoding="utf-8")
        proof_line = text[text.index("## Proof"):text.index("## Roadmap")]
        assert "`Theorem.`" in proof_line and "`Proof.`" in proof_line, name
        inject = text[text.index("- `Inject`"):text.index("- `ConfirmShelve`")]
        assert "This brick's `Theorem.` statement and `Proof.` argument" in inject, name
        assert "`Definition.`" in inject, name


def test_judge_and_worker_prompts_name_the_shape():
    adv = (_PROMPTS / "adversary" / "adversary.md").read_text(encoding="utf-8")
    assert "`Theorem.` statement then `Proof.` argument" in adv
    intake = (_PROMPTS / "formalizer" / "intake.md").read_text(encoding="utf-8")
    assert "`## Your assignment`" in intake and "settles this assignment" in intake
    formalize = (_PROMPTS / "formalizer" / "formalize.md").read_text(encoding="utf-8")
    assert "`Theorem.` is the claim, `Proof.` argues it" in formalize
