"""Axiom probe invariant — single gate for `goals.status='proved'`.

These tests enforce: every "mark proved" path runs `axiom_probe_file`
on the candidate proof, and rejects (via outcome='failed' or 'dead')
when the probe returns False.

Why it matters: `lake build` accepts files whose imports contain
`sorry` (sorry'd module compiles fine; sorryAx propagates through
definitions but lake returns rc=0). Only `#print axioms` walks the
kernel dependency graph and reports every axiom touched. Without the
probe, a strategy whose body is sorry-free but imports a shelved-
sub-goal stub gets marked 'proved' wrongly — exactly the SG s64 case
that motivated this layer.

Pipelines covered:
  - `verify_strategy` (`Tooling/verify.py`) — strategy assembly path
    used by both regular Backward decomposition AND Phase 6.5
    leaf-bypass salvage.
  - `_try_promote_sorry_free` (`pipeline/backward.py`) — sub-goal
    stub auto-promote when agent inlines a complete proof.

The conftest autouse fixture `_stub_axiom_probe_by_default` neutralises
the probe to (True, …) for non-axiom unit tests; tests here override
it locally to a False stub to exercise the rejection path.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from Tooling import agent, pipeline
from Tooling.state import db, manifest
from Tooling.quality import verify
from Tooling.pipeline import _axiom


# ---------------------------------------------------------------------
# Structural gate (2026-07-03) — every proved-producing pipeline must route
# its proved decision through the SHARED `_axiom.axiom_gate`. This is the
# achievable form of "unify the proved standard": Forward (commit_forward_
# lemma), Builder (leaf-bypass promote), and Backward (leaf-bypass) all call
# the one gate — a regression that adds a proved-flip without it, or removes
# the gate from one, trips here. (A runtime assert in apply_goal_transition is
# impractical: the gate runs in-pipeline on its own warm slot while some
# proved-flips fire dispatcher-side, and Forward's gate runs before insert_goal
# — so there is no goal_id-keyed flag to check at the transition.)
# ---------------------------------------------------------------------

_PIPELINE = Path(__file__).resolve().parents[1] / "Tooling" / "pipeline"


@pytest.mark.parametrize("name", ["forward.py", "backward.py"])
def test_proved_pipeline_uses_shared_axiom_gate(name) -> None:
    text = (_PIPELINE / name).read_text(encoding="utf-8")
    assert re.search(r"\baxiom_gate\s*\(", text), (
        f"{name} must route its proved decision through the shared "
        f"_axiom.axiom_gate (the single soundness gate for 'proved')")


# Cite-gate mirror of the structural test above (2026-07-04 convention
# audit, finding 4): every commit path that can write a
# `import Problems.<p>.proofs.L_<slug>` sibling citation must resolve it
# through the shared cite gate first (orphan-stub / dead / disproved
# citations rejected, auto-link / revive applied). Builder has one commit
# path; Backward has TWO (decomposition + leaf-bypass) — the count pins
# per-PATH coverage, not just per-file presence (the per-file grep above
# was blind to Builder P1's missing tripwire, finding 5). Forward doesn't
# cite via proofs-imports (its commit axiom gate's sorryAx tripwire is the
# backstop) — deliberately absent here.
@pytest.mark.parametrize("name,min_calls", [
    ("backward.py", 2),
])
def test_citing_commit_paths_use_shared_cite_gate(name, min_calls) -> None:
    text = (_PIPELINE / name).read_text(encoding="utf-8")
    n = len(re.findall(r"\b_resolve_cite_dependencies\s*\(", text))
    assert n >= min_calls, (
        f"{name}: expected ≥{min_calls} `_resolve_cite_dependencies(` call(s) "
        f"(one per citing commit path), found {n} — a commit path lost its "
        "cite gate, or a new one shipped without it")


# ---------------------------------------------------------------------
# Local fixture — point the probe to a False-returning stub for these
# tests, regardless of the global True stub from conftest.
# ---------------------------------------------------------------------

@pytest.fixture
def _reject_probe(monkeypatch: pytest.MonkeyPatch):
    """Replace the axiom-probing surface everywhere with a False-
    returning stub mirroring the SG s64 case (leaf-bypass sat on a
    shelved sibling's sorry stub).

    After verify-unification, axiom probing goes through TWO paths:
      1. `_axiom.axiom_probe(_file)` — direct callers (Builder
         Phase 1 hint, library.promote, etc.).
      2. `gateway_lifecycle.verify_file(..., axioms_for=...)` —
         verify_strategy / Builder Phase 2 verify use this. Reject
         via the `axioms` field returning a sorryAx; the rogue
         check happens client-side.
    """
    def _stub_reject(*args, **kwargs):
        return False, "rogue axioms: ['sorryAx']"
    monkeypatch.setattr(_axiom, "axiom_probe_file", _stub_reject)
    monkeypatch.setattr(_axiom, "axiom_probe", _stub_reject)

    from Tooling.lsp import lifecycle as _gl
    def _stub_verify_with_rogue(target_path, *, write_olean=True,
                                  axioms_for=None, decl_info=False,
                                  timeout=120.0,
                                  workspace=None):
        return {
            "ok": True,
            "diagnostic_count": 0,
            "diagnostics": [],
            "olean_written": write_olean,
            "olean_path": str(target_path),
            # Always include sorryAx so the client-side whitelist
            # check rejects regardless of which whitelist tests pass.
            "axioms": ["sorryAx"] if axioms_for else None,
            "axiom_error": None,
            "decl_info": None,
            "decl_info_error": None,
        }
    monkeypatch.setattr(_gl, "verify_file", _stub_verify_with_rogue)
    # The conftest autouse stubs verify_in_session to DELEGATE to verify_file
    # (call-time), so this override also drives the own-slot gate path.
    return _stub_reject


# ---------------------------------------------------------------------
# verify_strategy — rejects axiom-violation
# ---------------------------------------------------------------------

def _seed_goal_with_strategy(conn, tmp_path):
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    gid = db.insert_goal(
        conn, problem="p", slug="main",
        lean_path="Problems/p/proofs/L_main.lean",
        statement="True", origin="root", depth=0,
    )
    sid = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/proofs/L_main.lean",
        created_by="pid",
        scratch_path="Problems/p/proofs/_strategy_s.lean",
        proposal_md="-- main: leaf direct proof\n",
    )
    sub = db.insert_goal(
        conn, problem="p", slug="sub", origin="backward", depth=1,
        lean_path="Problems/p/proofs/L_sub.lean", statement="True",
    )
    db.update_goal_status(conn, sub, "proved")
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub, position=0)
    scratch = tmp_path / "Problems/p/proofs/_strategy_s.lean"
    scratch.parent.mkdir(parents=True)
    scratch.write_text("-- stub", encoding="utf-8")
    return gid, sid


def test_bisect_sorryax_finds_culprit_strategy(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root verify reported `rogue: [sorryAx]` and the framework must
    walk 'succeeded' strategies (deepest first) to find which non-leaf
    patch leaked it. Stub `verify_file` so that the strategy with
    matching scratch_fq returns sorryAx, others return clean.
    """
    _, sid = _seed_goal_with_strategy(conn, tmp_path)
    db.update_strategy_status(conn, sid, "succeeded")

    from Tooling.lsp import lifecycle as gateway_lifecycle

    def stub(target_path, *, write_olean=True, axioms_for=None,
             timeout=120.0, workspace=None):
        return {
            "ok": True,
            "diagnostic_count": 0,
            "diagnostics": [],
            "olean_written": False,
            "olean_path": None,
            # Only flag sorryAx when probing the seeded strategy's scratch_fq
            "axioms": ["sorryAx"] if axioms_for == f"Problems.p.s{sid}" else [],
            "axiom_error": None,
        }
    monkeypatch.setattr(gateway_lifecycle, "verify_file", stub)

    culprit = verify.bisect_sorryax_source(conn, tmp_path, "p")
    assert culprit is not None
    assert culprit["id"] == sid


def test_bisect_sorryax_returns_none_when_clean(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no 'succeeded' strategy carries sorryAx, bisect returns
    None (defensive — shouldn't happen if root probe truly reported
    sorryAx, but the caller logs + skips rather than crashing)."""
    _, sid = _seed_goal_with_strategy(conn, tmp_path)
    db.update_strategy_status(conn, sid, "succeeded")

    from Tooling.lsp import lifecycle as gateway_lifecycle

    def stub(target_path, *, write_olean=True, axioms_for=None,
             timeout=120.0, workspace=None):
        return {
            "ok": True, "diagnostic_count": 0, "diagnostics": [],
            "olean_written": False, "olean_path": None,
            "axioms": [] if axioms_for else None,
            "axiom_error": None,
        }
    monkeypatch.setattr(gateway_lifecycle, "verify_file", stub)
    assert verify.bisect_sorryax_source(conn, tmp_path, "p") is None


def test_rollback_cascade_chain_reverts_culprit_and_upstream(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rollback_cascade_chain walks from culprit upward, reverting
    both DB state and (via `rollback_promote`) parent file content.
    Culprit goes to 'dead' + goal 'open'; upstream stays alive
    (strategy 'proposed', goal 'attempting')."""
    # Two-level chain: parent strategy + culprit sub-strategy.
    grand_gid = _seed_goal_with_strategy.__wrapped__ if False else None  # noqa
    # Seed manually for clarity
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    grand_gid = db.insert_goal(
        conn, problem="p", slug="grand",
        lean_path="Problems/p/proofs/L_grand.lean",
        statement="T", origin="root", depth=0,
    )
    db.update_goal_status(conn, grand_gid, "proved")  # optimistic, will revert
    grand_sid = db.insert_strategy(
        conn, goal_id=grand_gid,
        lean_path="Problems/p/proofs/L_grand.lean",
        scratch_path="Problems/p/proofs/_strategy_grand.lean",
        created_by="pid_g",
    )
    db.update_strategy_status(conn, grand_sid, "succeeded")
    culprit_gid = db.insert_goal(
        conn, problem="p", slug="culprit",
        lean_path="Problems/p/proofs/L_culprit.lean",
        statement="T", origin="backward", depth=1,
    )
    db.update_goal_status(conn, culprit_gid, "proved")
    db.link_subgoal(conn, strategy_id=grand_sid,
                    subgoal_id=culprit_gid, position=0)
    culprit_sid = db.insert_strategy(
        conn, goal_id=culprit_gid,
        lean_path="Problems/p/proofs/L_culprit.lean",
        scratch_path="Problems/p/proofs/_strategy_culprit.lean",
        created_by="pid_c",
    )
    db.update_strategy_status(conn, culprit_sid, "succeeded")

    # Stub rollback_promote so we don't need real backup files on disk
    rollback_calls = []
    monkeypatch.setattr(
        verify, "rollback_promote",
        lambda parent_abs, backup: rollback_calls.append(parent_abs))

    rolled = verify.rollback_cascade_chain(conn, tmp_path, culprit_sid)
    assert rolled == 2

    # Culprit reverted to dead + open
    cs = conn.execute("SELECT status FROM strategies WHERE id = ?",
                      (culprit_sid,)).fetchone()
    cg = db.get_goal(conn, culprit_gid)
    assert cs["status"] == "dead"
    assert cg["status"] == "open"

    # Upstream reverted to proposed + attempting
    gs = conn.execute("SELECT status FROM strategies WHERE id = ?",
                      (grand_sid,)).fetchone()
    gg = db.get_goal(conn, grand_gid)
    assert gs["status"] == "proposed"
    assert gg["status"] == "attempting"


def test_cleanup_cascade_backups_unlinks_backup_files(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Happy path after root verify success: walk all 'succeeded'
    strategies, unlink any leftover backup files keyed by sid_token."""
    from Tooling.pipeline._skeleton import verify_backup_path
    _, sid = _seed_goal_with_strategy(conn, tmp_path)
    db.update_strategy_status(conn, sid, "succeeded")

    parent_abs = tmp_path / "Problems/p/proofs/L_main.lean"
    parent_abs.parent.mkdir(parents=True, exist_ok=True)
    parent_abs.write_text("-- parent", encoding="utf-8")
    backup = verify_backup_path(parent_abs, f"s{sid}")
    backup.write_text("-- backup contents", encoding="utf-8")
    assert backup.exists()

    n = verify.cleanup_cascade_backups(conn, tmp_path, "p")
    assert n == 1
    assert not backup.exists()


def test_verify_housekeeping_does_not_skip_probe_with_no_manifests(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`verify_strategy(manifests=None)` MUST be a test-only escape
    hatch — production callers (verify_housekeeping called from
    dispatcher) always pass the dispatcher's manifests dict. This test
    enforces that contract: when housekeeping receives a manifests dict,
    verify_strategy receives it too (probe is exercised)."""
    _, sid = _seed_goal_with_strategy(conn, tmp_path)
    received_manifests = {}

    def spy_verify(conn, *, workspace, strategy_id, manifests=None):
        received_manifests["v"] = manifests
        return "superseded"
    monkeypatch.setattr(verify, "verify_strategy", spy_verify)

    mfst = manifest.Manifest(problem="p", body="True",
                              axioms_whitelist=["propext"])
    verify.verify_housekeeping(
        conn, workspace=tmp_path, manifests={"p": mfst},
    )
    assert received_manifests["v"] == {"p": mfst}


# ---------------------------------------------------------------------
# root_integrity_gate — library opt-in enqueues the Librarian (Phase 2)
# ---------------------------------------------------------------------

def _seed_proved_root(conn, problem="p"):
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        (problem, f"Problems/{problem}/Manifest.md", db.now()),
    )
    gid = db.insert_goal(
        conn, problem=problem, slug="main",
        lean_path=f"Problems/{problem}/proofs/L_main.lean",
        statement="True", origin="root", depth=0,
    )
    db.update_goal_status(conn, gid, "proved")
    return gid


def _queue_rows(conn):
    return list(conn.execute(
        "SELECT kind, target_id, target_kind, priority FROM queue"))


def test_gate_does_not_enqueue_librarian_even_when_library_optin(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Phase 6 — the root-proved auto-Librarian trigger is RETIRED:
    harvest is strictly Ingest-driven (strategist._commit_ingest owns
    the enqueue, behind the sign-off gate). A clean, fully-proved root
    with `library: true` opt-in passes the gate (integrity_verified
    set) but enqueues NOTHING. The autouse conftest stub returns an
    axiom-clean probe → happy path."""
    gid = _seed_proved_root(conn)
    mfst = manifest.Manifest(problem="p", body="True", library=True)
    verify.root_integrity_gate(conn, tmp_path, "p", mfst)
    assert _queue_rows(conn) == []
    row = conn.execute(
        "SELECT integrity_verified FROM goals WHERE id = ?", (gid,),
    ).fetchone()
    assert row["integrity_verified"] == 1


def test_gate_no_librarian_when_library_optout(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Default (`library` unset) must NOT harvest — opt-in only."""
    _seed_proved_root(conn)
    mfst = manifest.Manifest(problem="p", body="True")
    verify.root_integrity_gate(conn, tmp_path, "p", mfst)
    assert _queue_rows(conn) == []


def test_gate_no_librarian_on_rogue_axiom_even_if_optin(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dirty root (rogue axioms) must never be harvested, even with
    the opt-in set — the gate returns at the probe-failure branch,
    before the integrity-verified + enqueue block."""
    _seed_proved_root(conn)
    monkeypatch.setattr("Tooling.pipeline._axiom.axiom_probe",
                        lambda *a, **k: (False, "rogue axioms: ['sorryAx']"))
    # Stub the cascade bisect (it would otherwise reach the real
    # gateway). None mirrors "sorryAx at root but no source found" —
    # the gate logs and returns without enqueueing.
    monkeypatch.setattr(verify, "bisect_sorryax_source",
                        lambda *a, **k: None)
    mfst = manifest.Manifest(problem="p", body="True", library=True)
    verify.root_integrity_gate(conn, tmp_path, "p", mfst)
    assert _queue_rows(conn) == []


def test_gate_root_file_baseline_pin(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Self-audit 2026-07-12 §3-3: a proved root verifies ONLY if
    Root.lean still matches its recorded baseline — the mechanical
    equality between 'proved' and the original contract. Tampered
    bytes → early return BEFORE the axiom probe, integrity_verified
    stays 0; an operator `repin` row re-accepts the current bytes."""
    gid = _seed_proved_root(conn)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    root = pdir / "Root.lean"
    root.write_text("theorem main : True := by sorry\n", encoding="utf-8")
    baseline_sha = manifest._content_sha(
        root.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO user_file_history"
        " (problem, file, sha, body, seen_at, source)"
        " VALUES ('p', 'Root.lean', ?, ?, ?, 'observed')",
        (baseline_sha, root.read_text(encoding="utf-8"), db.now()))
    conn.commit()

    # Tamper the statement mid-run — probe must NOT even run.
    root.write_text("theorem main : False := by sorry\n", encoding="utf-8")

    def _probe_must_not_run(*a, **k):
        raise AssertionError("axiom_probe ran on a tampered root")
    monkeypatch.setattr("Tooling.pipeline._axiom.axiom_probe",
                        _probe_must_not_run)
    mfst = manifest.Manifest(problem="p", body="True")
    verify.root_integrity_gate(conn, tmp_path, "p", mfst)
    row = conn.execute(
        "SELECT integrity_verified FROM goals WHERE id = ?", (gid,),
    ).fetchone()
    assert row["integrity_verified"] == 0

    # Operator acknowledges the change (repin) → gate passes again.
    monkeypatch.setattr("Tooling.pipeline._axiom.axiom_probe",
                        lambda *a, **k: (True, "(3 axioms ok)"))
    cur_sha = manifest._content_sha(root.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO user_file_history"
        " (problem, file, sha, body, seen_at, source)"
        " VALUES ('p', 'Root.lean', ?, ?, ?, 'repin')",
        (cur_sha, root.read_text(encoding="utf-8"), db.now()))
    conn.commit()
    verify.root_integrity_gate(conn, tmp_path, "p", mfst)
    row = conn.execute(
        "SELECT integrity_verified FROM goals WHERE id = ?", (gid,),
    ).fetchone()
    assert row["integrity_verified"] == 1


def _seed_pinned_root_stub(conn, tmp_path, stmt="True"):
    """Proved root + on-disk Root.lean stub + first-load baseline row.
    Shared setup for the task-#120 statement-pin cases."""
    gid = _seed_proved_root(conn)
    conn.execute("UPDATE goals SET statement = ? WHERE id = ?",
                 (stmt, gid))
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    root = pdir / "Root.lean"
    root.write_text(f"theorem main : {stmt} := by sorry\n",
                    encoding="utf-8")
    body = root.read_text(encoding="utf-8")
    conn.execute(
        "INSERT INTO user_file_history"
        " (problem, file, sha, body, seen_at, source)"
        " VALUES ('p', 'Root.lean', ?, ?, ?, 'observed')",
        (manifest._content_sha(body), body, db.now()))
    conn.commit()
    return gid, root


def test_gate_statement_pin_accepts_root_proof_body_rewrite(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Task #120: the framework's own root-proof landing (Builder
    assembly writes the proof into Root.lean) changes the file bytes
    but NOT the statement — the pin must accept it. Baseline stub +
    rewritten file carrying the byte-identical `theorem main : <stmt>`
    → gate proceeds to the (conftest-stubbed, clean) axiom probe and
    verifies the root."""
    gid, root = _seed_pinned_root_stub(conn, tmp_path)
    root.write_text(
        "import Mathlib\n"
        "import Problems.p.proofs.L_left\n\n"
        "-- assembled by Builder\n"
        "theorem main : True := by\n  trivial\n",
        encoding="utf-8")
    mfst = manifest.Manifest(problem="p", body="True")
    verify.root_integrity_gate(conn, tmp_path, "p", mfst)
    row = conn.execute(
        "SELECT integrity_verified FROM goals WHERE id = ?", (gid,),
    ).fetchone()
    assert row["integrity_verified"] == 1


def test_gate_statement_pin_rejects_edited_statement_in_proof_body(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A proof-body-style rewrite whose statement TEXT drifted from the
    pin is still a violation — probe must not run."""
    gid, root = _seed_pinned_root_stub(conn, tmp_path)
    root.write_text("theorem main : 1 = 1 := by\n  rfl\n",
                    encoding="utf-8")
    monkeypatch.setattr(
        "Tooling.pipeline._axiom.axiom_probe",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("axiom_probe ran on a statement-drifted root")))
    mfst = manifest.Manifest(problem="p", body="True")
    verify.root_integrity_gate(conn, tmp_path, "p", mfst)
    row = conn.execute(
        "SELECT integrity_verified FROM goals WHERE id = ?", (gid,),
    ).fetchone()
    assert row["integrity_verified"] == 0


def test_gate_statement_pin_def_alias_own_strategy_passes(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Verify-promote / prune-reconcile write the def-alias form
    (`def main := @Problems.p.s<N>`), which erases the statement text.
    Accepted iff s<N> is this root's own 'succeeded' strategy — its
    decl signature was locked to goals.statement at commit."""
    gid, root = _seed_pinned_root_stub(conn, tmp_path)
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, created_by, created_at)"
        " VALUES (?, 'Problems/p/Root.lean',"
        " 'Problems/p/proofs/_strategy_s1.lean', 'succeeded',"
        " 'test', ?)", (gid, db.now()))
    sid = cur.lastrowid
    root.write_text(
        "import Mathlib\nimport Problems.p.proofs._strategy_s1\n\n"
        "namespace Problems.p\n\n"
        f"def main := @Problems.p.s{sid}\n\n"
        "end Problems.p\n",
        encoding="utf-8")
    mfst = manifest.Manifest(problem="p", body="True")
    verify.root_integrity_gate(conn, tmp_path, "p", mfst)
    row = conn.execute(
        "SELECT integrity_verified FROM goals WHERE id = ?", (gid,),
    ).fetchone()
    assert row["integrity_verified"] == 1


def test_gate_statement_pin_def_alias_foreign_strategy_blocked(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A def-alias citing a strategy that is NOT this root's succeeded
    strategy proves an unpinned type — violation, probe must not run."""
    gid, root = _seed_pinned_root_stub(conn, tmp_path)
    other = db.insert_goal(
        conn, problem="p", slug="other",
        lean_path="Problems/p/proofs/L_other.lean",
        statement="False", origin="backward", depth=1)
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, created_by, created_at)"
        " VALUES (?, 'Problems/p/proofs/L_other.lean',"
        " 'Problems/p/proofs/_strategy_s9.lean', 'succeeded',"
        " 'test', ?)", (other, db.now()))
    sid = cur.lastrowid
    root.write_text(
        f"namespace Problems.p\n\ndef main := @Problems.p.s{sid}\n\n"
        "end Problems.p\n",
        encoding="utf-8")
    monkeypatch.setattr(
        "Tooling.pipeline._axiom.axiom_probe",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("axiom_probe ran on a foreign-alias root")))
    mfst = manifest.Manifest(problem="p", body="True")
    verify.root_integrity_gate(conn, tmp_path, "p", mfst)
    row = conn.execute(
        "SELECT integrity_verified FROM goals WHERE id = ?", (gid,),
    ).fetchone()
    assert row["integrity_verified"] == 0


def test_gate_statement_pin_defs_lean_still_whole_file(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defs.lean has no sanctioned framework writer — vocabulary drift
    changes the statement's MEANING with identical statement text, so
    it keeps the whole-file pin. Root.lean untouched + Defs.lean edited
    → blocked before the probe."""
    gid, _root = _seed_pinned_root_stub(conn, tmp_path)
    defs = tmp_path / "Problems" / "p" / "Defs.lean"
    defs.write_text("def f := 1\n", encoding="utf-8")
    body = defs.read_text(encoding="utf-8")
    conn.execute(
        "INSERT INTO user_file_history"
        " (problem, file, sha, body, seen_at, source)"
        " VALUES ('p', 'Defs.lean', ?, ?, ?, 'observed')",
        (manifest._content_sha(body), body, db.now()))
    conn.commit()
    defs.write_text("def f := 2\n", encoding="utf-8")
    monkeypatch.setattr(
        "Tooling.pipeline._axiom.axiom_probe",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("axiom_probe ran on vocabulary drift")))
    mfst = manifest.Manifest(problem="p", body="True")
    verify.root_integrity_gate(conn, tmp_path, "p", mfst)
    row = conn.execute(
        "SELECT integrity_verified FROM goals WHERE id = ?", (gid,),
    ).fetchone()
    assert row["integrity_verified"] == 0


# ---------------------------------------------------------------------
# verify_on_own_slot — the pipeline=slot dispatch (2026-07-03): a session
# token in attempts_dir routes to verify_in_session (the pipeline's own
# claimed slot); no token falls back to the borrowed verify_file path.
# The three former in-pipeline borrows (forward self_verify, forward alias
# build-verify, backward sorry-free promotion) all route through this now.
# ---------------------------------------------------------------------

def test_verify_on_own_slot_dispatches_by_token(tmp_path, monkeypatch):
    from Tooling.pipeline import _axiom
    from Tooling.lsp import lifecycle as gl
    src = tmp_path / "f.lean"
    src.write_text("theorem t : True := trivial\n", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(gl, "verify_in_session",
                        lambda *a, **k: calls.append("session") or {"ok": True})
    monkeypatch.setattr(gl, "verify_file",
                        lambda *a, **k: calls.append("borrow") or {"ok": True})

    # no attempts_dir / no token file → borrow fallback
    _axiom.verify_on_own_slot(src, workspace=tmp_path)
    assert calls == ["borrow"]

    # token present → own slot, never borrow
    calls.clear()
    adir = tmp_path / ".attempts" / "p1"
    adir.mkdir(parents=True)
    (adir / "_gateway_session.token").write_text("tok123", encoding="utf-8")
    _axiom.verify_on_own_slot(src, workspace=tmp_path, attempts_dir=adir)
    assert calls == ["session"]


# Captured at import time (= collection), BEFORE the conftest autouse stub
# replaces them — same pattern as test_gateway_lifecycle's real-fn restore.
from Tooling.pipeline import _axiom as _axiom_mod  # noqa: E402
_REAL_AXIOM_PROBE = _axiom_mod.axiom_probe
_REAL_AXIOM_PROBE_FILE = _axiom_mod.axiom_probe_file


def test_axiom_probe_file_threads_attempts_dir(tmp_path, monkeypatch):
    from Tooling.pipeline import _axiom
    from Tooling.lsp import lifecycle as gl
    # conftest autouse stubs axiom_probe_file/axiom_probe wholesale; this test
    # exercises the REAL functions' own-slot dispatch — restore them.
    monkeypatch.setattr(_axiom, "axiom_probe", _REAL_AXIOM_PROBE)
    monkeypatch.setattr(_axiom, "axiom_probe_file", _REAL_AXIOM_PROBE_FILE)
    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    dest = proofs / "L_foo.lean"
    dest.write_text("theorem foo : True := trivial\n", encoding="utf-8")
    adir = tmp_path / ".attempts" / "p2"
    adir.mkdir(parents=True)
    (adir / "_gateway_session.token").write_text("tok456", encoding="utf-8")
    seen: dict = {}

    def fake_session(token, content, **k):
        seen["token"] = token
        return {"ok": True, "axioms": []}
    monkeypatch.setattr(gl, "verify_in_session", fake_session)
    monkeypatch.setattr(
        gl, "verify_file",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("must not borrow when a token is present")))
    ok, msg = _axiom.axiom_probe_file(
        tmp_path, dest, problem="p", slug="foo",
        whitelist=["propext"], attempts_dir=adir)
    assert ok, msg
    assert seen["token"] == "tok456"
