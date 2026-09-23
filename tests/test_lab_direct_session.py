"""The direct-session experiment runner's pure verdict functions.

The runner itself spawns an agent and shells out to `lake`; what is
tested here is everything that decides what a run MEANT — statement
fidelity, the axiom reading, the gateway log tally, the declaration
count. Those are the numbers the comparison between the three arms is
made of, so they are the part that must not be wrong.
"""
from __future__ import annotations

import json

from Tooling.lab import direct_session as ds


# --- statement fidelity ----------------------------------------------

_ROOT = (
    "import Mathlib\n"
    "namespace Problems.Combinatorics.single_root_direct\n"
    "\n"
    "theorem main :\n"
    "    forall (n : Nat), 0 < n ->\n"
    "    n * 2 <= 2 * n := by\n"
    "  sorry\n"
    "\n"
    "end Problems.Combinatorics.single_root_direct\n"
)


def test_main_statement_is_read_from_the_colon_to_the_body():
    assert ds.main_statement(_ROOT) == "forall (n : Nat), 0 < n -> n * 2 <= 2 * n"
    assert ds.main_statement("theorem other : True := trivial\n") is None


def test_statements_identical_ignores_layout_but_not_a_hypothesis():
    reflowed = _ROOT.replace(
        "theorem main :\n    forall (n : Nat), 0 < n ->\n    n * 2 <= 2 * n",
        "theorem main : forall (n : Nat),   0 < n -> n * 2 <= 2 * n"
    ).replace("  sorry\n", "  omega\n")
    assert ds.statements_identical(_ROOT, reflowed)

    weakened = _ROOT.replace("0 < n ->", "0 <= n ->")
    assert not ds.statements_identical(_ROOT, weakened)


# --- axioms + verdict -------------------------------------------------

_AXIOM_LINE = (
    "'Problems.Combinatorics.single_root_direct.main' depends on axioms: "
    "[propext, Classical.choice, Quot.sound]"
)


def test_axioms_are_parsed_from_the_print_axioms_line():
    assert ds.parse_axioms(_AXIOM_LINE) == [
        "propext", "Classical.choice", "Quot.sound"]
    assert ds.parse_axioms("no axiom line here") is None


def test_verdict_clean_sorry_and_extra_axiom():
    clean = ds.verdict(0, _AXIOM_LINE, ds.parse_axioms(_AXIOM_LINE))
    assert clean == "proved"

    sorried = (_AXIOM_LINE.replace("Quot.sound]", "Quot.sound, sorryAx]")
               + "\nRoot.lean:7:0: warning: declaration uses 'sorry'\n")
    assert ds.has_sorry_warning(sorried)
    assert ds.verdict(0, sorried, ds.parse_axioms(sorried)) == "failed"

    extra = _AXIOM_LINE.replace("Quot.sound]", "Quot.sound, myAxiom]")
    assert ds.verdict(0, extra, ds.parse_axioms(extra)) == "failed"

    # A non-zero lake rc is a failure whatever the text says, and a run
    # that never finished is neither proved nor disproved.
    assert ds.verdict(1, _AXIOM_LINE, ds.parse_axioms(_AXIOM_LINE)) == "failed"
    assert ds.verdict(0, "", None, timed_out=True) == "timeout"


# --- gateway log ------------------------------------------------------

def test_gateway_tool_counts_from_the_session_jsonl(tmp_path):
    log = tmp_path / "direct_lsp_r1.jsonl"
    log.write_text("\n".join(json.dumps(e) for e in (
        {"ts": "t0", "event": "session_registered", "pipeline_id": "p"},
        {"ts": "t1", "event": "tool_call", "name": "validate_file",
         "has_error": True, "timed_out": False, "diagnostic_count": 3},
        {"ts": "t2", "event": "tool_call", "name": "errors_at",
         "converged": True, "returned_count": 0},
        {"ts": "t3", "event": "tool_call", "name": "validate_file",
         "has_error": False, "timed_out": False, "diagnostic_count": 0},
    )) + "\n", encoding="utf-8")

    got = ds.gateway_tool_counts(log)
    assert got["tools"] == {"validate_file": 2, "errors_at": 1}
    assert got["validate_ok"] == 1
    assert got["validate_fail"] == 1
    assert got["elab_wall"] == 0
    assert got["last_validate_ok"] is True

    # No log at all (the `shell` arm registers no session).
    absent = ds.gateway_tool_counts(tmp_path / "nothing.jsonl")
    assert absent["tools"] == {} and absent["last_validate_ok"] is None


def test_gateway_tool_counts_see_the_elaboration_wall(tmp_path):
    log = tmp_path / "walled.jsonl"
    log.write_text(json.dumps(
        {"event": "tool_call", "name": "validate_file",
         "has_error": False, "timed_out": True,
         "diagnostic_count": None}) + "\n", encoding="utf-8")
    got = ds.gateway_tool_counts(log)
    assert got["elab_wall"] == 1
    assert got["validate_ok"] == 0 and got["validate_fail"] == 1
    assert got["last_validate_ok"] is False


# --- declaration count ------------------------------------------------

def test_decl_count_counts_top_level_heads_only():
    text = (
        "import Mathlib\n"
        "namespace N\n"
        "theorem a : True := trivial\n"
        "lemma b : True := trivial\n"
        "noncomputable def c : Nat := 1\n"
        "abbrev d : Nat := 2\n"
        "instance e : Inhabited Nat := Nat.instInhabited\n"
        "theorem f : True := by\n"
        "  have h : True := trivial\n"
        "  exact h\n"
        # Indented: a declaration inside a section body, not one of the
        # file's own heads.
        "  theorem nested : True := trivial\n"
        "end N\n"
    )
    assert ds.decl_count(text) == 6
