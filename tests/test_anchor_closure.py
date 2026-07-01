"""Anchor closure probe (`Tooling/pipeline/_constants.py`) — the
anchor+claim architecture's TCB (`docs/internal/anchor_claim_design.md`
§4).

Two layers:
  * Unit tests (default suite): mock `verify_file` and assert
    `anchor_closure` parses the gateway response into `AnchorClosure`
    correctly — the anchor/claim partition and every failure mode.
  * `real_lake` integration test (opt-in): drives a live gateway over
    a purpose-built fixture and asserts the KERNEL walk's invariants —
    transitive def closure, trusted pruning, claim-vs-anchor via
    `isProp`, no proof leak through a `def := proof` wrapper, and
    regex-trap immunity (docstring tokens produce no phantom decls).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from Tooling.pipeline import _constants
from Tooling.pipeline._constants import AnchorClosure, anchor_closure


# ---------------------------------------------------------------------------
# Unit: response parsing + partition + failure modes (mock verify_file)
# ---------------------------------------------------------------------------

def _mk_source(tmp_path: Path, module: str) -> Path:
    src = tmp_path / Path(*module.split(".")).with_suffix(".lean")
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("-- placeholder\n", encoding="utf-8")
    return src


def _patch_verify(monkeypatch, result: dict) -> None:
    from Tooling.lsp import lifecycle as gl
    monkeypatch.setattr(gl, "verify_file", lambda *a, **k: result)


def test_parses_clean_closure_and_partitions(tmp_path, monkeypatch):
    _mk_source(tmp_path, "M.Probe")
    _patch_verify(monkeypatch, {
        "ok": True,
        "diagnostics": [],
        "top_kind": "thm",
        "top_is_prop": True,
        "top_module": "",
        "pending_anchors": [
            {"name": "M.Probe.myAnchor", "module": "", "kind": "def"},
            {"name": "M.Probe.helperLemma", "module": "M.Probe", "kind": "thm"},
        ],
        "closure_error": None,
    })
    r = anchor_closure(tmp_path, fq_name="M.Probe.myClaim", module="M.Probe")
    assert r.ok and r.error is None
    assert r.top_kind == "thm"
    assert r.top_is_prop is True and r.top_is_claim is True
    # def → anchor; thm → claim
    assert [c["name"] for c in r.anchors] == ["M.Probe.myAnchor"]
    assert [c["name"] for c in r.claims] == ["M.Probe.helperLemma"]


def test_data_deliverable_is_not_a_claim(tmp_path, monkeypatch):
    _mk_source(tmp_path, "M.Probe")
    _patch_verify(monkeypatch, {
        "ok": True, "diagnostics": [],
        "top_kind": "def", "top_is_prop": False, "top_module": "M.Probe",
        "pending_anchors": [], "closure_error": None,
    })
    r = anchor_closure(tmp_path, fq_name="M.Probe.myData", module="M.Probe")
    assert r.ok and r.top_is_claim is False and r.pending == []


def test_source_not_found_is_not_ok(tmp_path):
    # No file written → resolution fails before any gateway call.
    r = anchor_closure(tmp_path, fq_name="M.Probe.x", module="M.Probe")
    assert r.ok is False and "source not found" in (r.error or "")


def test_verify_error_diagnostics_surface(tmp_path, monkeypatch):
    _mk_source(tmp_path, "M.Probe")
    _patch_verify(monkeypatch, {
        "ok": False,
        "diagnostics": [{"severity": "error", "message": "unknown identifier 'foo'"}],
    })
    r = anchor_closure(tmp_path, fq_name="M.Probe.x", module="M.Probe")
    assert r.ok is False and "unknown identifier" in (r.error or "")


def test_closure_error_surfaces(tmp_path, monkeypatch):
    _mk_source(tmp_path, "M.Probe")
    _patch_verify(monkeypatch, {
        "ok": True, "diagnostics": [],
        "closure_error": "constant not found: M.Probe.x",
    })
    r = anchor_closure(tmp_path, fq_name="M.Probe.x", module="M.Probe")
    assert r.ok is False and "constant not found" in (r.error or "")


def test_infra_error_surfaces(tmp_path, monkeypatch):
    _mk_source(tmp_path, "M.Probe")
    _patch_verify(monkeypatch, {"error": "gateway unreachable", "transient": True})
    r = anchor_closure(tmp_path, fq_name="M.Probe.x", module="M.Probe")
    assert r.ok is False and "gateway unreachable" in (r.error or "")


def test_empty_closure_ok(tmp_path, monkeypatch):
    _mk_source(tmp_path, "M.Probe")
    _patch_verify(monkeypatch, {
        "ok": True, "diagnostics": [],
        "top_kind": "thm", "top_is_prop": True,
        "pending_anchors": [], "closure_error": None,
    })
    r = anchor_closure(tmp_path, fq_name="M.Probe.x", module="M.Probe")
    assert r.ok and r.pending == [] and r.anchors == [] and r.claims == []


# ---------------------------------------------------------------------------
# DB: is_deliverable column + mark_deliverable / deliverables helpers
# ---------------------------------------------------------------------------

from Tooling.state import db as _db


def _seed_goal(conn, problem: str, slug: str) -> int:
    conn.execute("INSERT OR IGNORE INTO problems(name, manifest_path, created_at)"
                 " VALUES (?,?,?)", (problem, f"{problem}/Manifest.md", _db.now()))
    return _db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=f"Problems/{problem}/proofs/L_{slug}.lean",
        statement="True", origin="forward", status="proved", kind="theorem")


def test_schema_has_is_deliverable(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(goals)")}
    assert "is_deliverable" in cols


def test_mark_and_list_deliverables(conn):
    g1 = _seed_goal(conn, "P.a", "foo")
    g2 = _seed_goal(conn, "P.a", "bar")
    _seed_goal(conn, "P.b", "baz")
    assert _db.deliverables(conn) == []            # default 0
    _db.mark_deliverable(conn, g1)
    _db.mark_deliverable(conn, g2)
    got = {(r["problem"], r["slug"]) for r in _db.deliverables(conn)}
    assert got == {("P.a", "foo"), ("P.a", "bar")}
    # scope filter
    assert {r["id"] for r in _db.deliverables(conn, problem="P.a")} == {g1, g2}
    assert _db.deliverables(conn, problem="P.b") == []
    # idempotent unmark
    _db.mark_deliverable(conn, g1, False)
    assert {r["id"] for r in _db.deliverables(conn)} == {g2}


def test_mark_deliverable_decision_only_on_forward(conn):
    from Tooling.pipeline.strategist import Decision, verify_decision
    fwd = _seed_goal(conn, "P.a", "foo")  # origin='forward'
    root = _db.insert_goal(
        conn, problem="P.a", slug="main",
        lean_path="Problems/P.a/Root.lean", statement="True",
        origin="root", status="proved")
    # Forward node → accepted
    assert verify_decision(
        Decision(kind="MarkDeliverable", target_id=fwd),
        conn, problem="P.a") == ""
    # Root (hand-written, author-vouched) → rejected
    err = verify_decision(
        Decision(kind="MarkDeliverable", target_id=root),
        conn, problem="P.a")
    assert "origin='forward'" in err
    # Missing target → rejected
    assert "requires target" in verify_decision(
        Decision(kind="MarkDeliverable"), conn, problem="P.a")
    # Wrong problem → rejected
    assert "belongs to problem" in verify_decision(
        Decision(kind="MarkDeliverable", target_id=fwd),
        conn, problem="P.other")


# ---------------------------------------------------------------------------
# Integration (real_lake): the actual kernel walk over a live gateway
# ---------------------------------------------------------------------------

_FIXTURE = """import Mathlib

namespace Problems.AnchorClosureLiveTest.Probe

/-- Prose docstring naming def, structure, class, theorem, instance,
abbrev, lemma of tokens — a text/regex decl scanner would hallucinate
phantom decls; the kernel walk must ignore all of it. -/
def myAnchor : Nat := 5

/-- A second generated def the claim's statement leans on. -/
def myOtherAnchor : Nat := myAnchor + 2

theorem myClaim : myOtherAnchor = 7 := by decide

/-- Framework root shape `def main := proof`: type is a Prop, value is
a proof term (`myClaim`). Must be treated as a claim — statement only —
so `myClaim` must NOT leak into its closure. -/
def mainWrapper : myOtherAnchor = 7 := myClaim

/-- A data def whose body carries a proof obligation — Lean emits an
internal `_proof_N` auxiliary. It is proof-irrelevant and must be
filtered from any closure via `Name.isInternalDetail`. -/
def myProofBearing : {n : Nat // 0 < n} := ⟨myOtherAnchor, by decide⟩

theorem claimUsingProofBearing : myProofBearing.val = 7 := by decide

end Problems.AnchorClosureLiveTest.Probe
"""


@pytest.mark.real_lake
def test_anchor_closure_live_kernel_walk():
    """End-to-end TCB behavior on a live gateway. Opt in with
    `ASTERISM_REAL_LAKE=1 pytest -m real_lake -k anchor_closure_live`.
    Reuses a running gateway if present; otherwise warms one (slow)."""
    from Tooling.lsp import lifecycle as gl

    workspace = Path(__file__).resolve().parents[1]
    mod = "Problems.AnchorClosureLiveTest.Probe"
    src = workspace / Path(*mod.split(".")).with_suffix(".lean")
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(_FIXTURE, encoding="utf-8")
    try:
        gl.start_gateway(workspace)

        def names(r: AnchorClosure) -> set[str]:
            return {c["name"].rsplit(".", 1)[-1] for c in r.pending}

        # A real theorem: claim, statement-only walk, transitive def closure.
        rc = anchor_closure(workspace, fq_name=f"{mod}.myClaim", module=mod)
        assert rc.ok, rc.error
        assert rc.top_is_prop is True and rc.top_kind == "thm"
        assert names(rc) == {"myAnchor", "myOtherAnchor"}
        # trusted pruning: Nat/Eq/OfNat/HAdd/... never surface
        assert all(c["kind"] == "def" for c in rc.pending)

        # The `def := proof` wrapper: still a claim (isProp), and the proof
        # term `myClaim` must NOT leak — the whole point of the isProp guard.
        rw = anchor_closure(workspace, fq_name=f"{mod}.mainWrapper", module=mod)
        assert rw.ok, rw.error
        assert rw.top_is_prop is True and rw.top_kind == "def"
        assert names(rw) == {"myAnchor", "myOtherAnchor"}
        assert "myClaim" not in names(rw), "proof term leaked into closure"

        # Regex-trap immunity: docstring tokens produce no phantom decls.
        phantoms = names(rc) & {"of", "def", "structure", "class",
                                "theorem", "instance", "abbrev", "lemma"}
        assert not phantoms, f"phantom decls from prose: {phantoms}"

        # Compiler-generated `_proof_N` auxiliaries must be filtered: the
        # data def `myProofBearing`'s body carries a `by decide` obligation.
        rp = anchor_closure(workspace, fq_name=f"{mod}.claimUsingProofBearing",
                            module=mod)
        assert rp.ok, rp.error
        pnames = {c["name"] for c in rp.pending}
        assert any(n.endswith(".myProofBearing") for n in pnames)
        assert not any("_proof" in n or n.rsplit(".", 1)[-1].startswith("_")
                       for n in pnames), f"internal-detail leaked: {pnames}"
    finally:
        shutil.rmtree(src.parent, ignore_errors=True)
