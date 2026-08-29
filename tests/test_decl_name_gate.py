"""Owner ruling 2026-08-29: a brick's top-level names are checked as
STRINGS against every file already under the problem (proved, alive
and shelved alike) before it lands — and before the kernel ever sees
it. A collision is refused with the way out named (cite the existing
decl, or rename a genuinely different concept); the framework's own
generated slugs keep their auto-suffix.

The incident: two shelved leftovers (`L_four_packet_mask_certificate`,
`L_four_packet_boolean_cert`) each carried a private copy of
`four_packet_valid` / `four_packet_family` / `four_packet_ineq` in the
problem namespace. Alone each built; imported together Lean stopped
at `environment already contains`, and the dedupe probe — which
imports every canonical it wants to compare against — refused all
pairs, 8 batches out of 10, silently. Eight such names existed, every
one involving a shelved residue file."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.quality import names
from Tooling.state import db

_DEFS = """import Mathlib

namespace Problems.p

def ucf_bound : Nat := 3

end Problems.p
"""

_BRICK_A = """import Mathlib

namespace Problems.p

abbrev four_packet_family := Finset (Finset (Fin 4))

def four_packet_valid (K : four_packet_family) : Prop := True

theorem brick_a : True := trivial

end Problems.p
"""

# A different brick that re-invents two of A's helpers under the same
# names (and adds one of its own, `fp_trace_code`).
_BRICK_B = """import Mathlib

namespace Problems.p

abbrev four_packet_family := Finset (Finset (Fin 4))

def four_packet_valid (K : four_packet_family) : Prop := K.card ≤ 4

def fp_trace_code (T : Finset (Fin 4)) : Fin 16 := ⟨0, by decide⟩

theorem brick_b : True := trivial

end Problems.p
"""


def _problem(tmp_path: Path) -> Path:
    pdir = tmp_path / "Problems" / "p"
    (pdir / "proofs").mkdir(parents=True)
    (pdir / "Defs.lean").write_text(_DEFS, encoding="utf-8")
    (pdir / "proofs" / "L_brick_a.lean").write_text(_BRICK_A, encoding="utf-8")
    return pdir


# ------------------------------------------------------------ parsing

def test_top_level_names_track_namespaces_and_skip_what_cannot_collide():
    text = """import Mathlib
/- def commented_out : Nat := 0 -/
-- def also_commented : Nat := 0
namespace A.B

@[simp] lemma simp_lemma : True := trivial
noncomputable def nc (x : Nat) : Nat := x
protected def prot : Nat := 0
private def hidden : Nat := 0
instance : Inhabited Nat := ⟨0⟩
instance named_inst : Inhabited Nat := ⟨0⟩
structure S where
  x : Nat
inductive I | a | b
theorem t : True := by
  have inner : True := trivial
  let def_like := 1
  exact trivial

section
def in_section : Nat := 0
end

end A.B

def top : Nat := 0
"""
    got = {n: k for n, k, _line in names.top_level_names(text)}
    assert got == {
        "A.B.simp_lemma": "lemma",
        "A.B.nc": "def",
        "A.B.prot": "def",
        "A.B.named_inst": "instance",
        "A.B.S": "structure",
        "A.B.I": "inductive",
        "A.B.t": "theorem",
        "A.B.in_section": "def",
        "top": "def",
    }, "comments, private decls, anonymous instances and nested lines are not collision surface"


def test_name_index_covers_proofs_defs_and_root(tmp_path: Path):
    pdir = _problem(tmp_path)
    (pdir / "Root.lean").write_text(
        "namespace Problems.p\ntheorem root_thm : True := trivial\nend Problems.p\n",
        encoding="utf-8")
    idx = names.name_index(pdir)
    assert idx["Problems.p.four_packet_valid"] == "proofs/L_brick_a.lean"
    assert idx["Problems.p.ucf_bound"] == "Defs.lean"
    assert idx["Problems.p.root_thm"] == "Root.lean"


def test_collisions_ignore_the_files_own_names_and_name_the_other_file(
        tmp_path: Path):
    pdir = _problem(tmp_path)
    assert names.collisions(pdir, _BRICK_A, own_rel="proofs/L_brick_a.lean") == []
    hits = names.collisions(pdir, _BRICK_B, own_rel="proofs/L_brick_b.lean")
    assert {(h.name, h.existing) for h in hits} == {
        ("Problems.p.four_packet_family", "proofs/L_brick_a.lean"),
        ("Problems.p.four_packet_valid", "proofs/L_brick_a.lean"),
    }
    # the brick's own theorem and its genuinely new helper are not collisions
    assert all(h.name != "Problems.p.fp_trace_code" for h in hits)


def test_teaching_names_the_file_and_both_ways_out(tmp_path: Path):
    pdir = _problem(tmp_path)
    hits = names.collisions(pdir, _BRICK_B, own_rel="proofs/L_brick_b.lean")
    msg = names.teaching(hits)
    assert "four_packet_valid" in msg and "proofs/L_brick_a.lean" in msg
    assert "cite" in msg.lower() and "rename" in msg.lower()


def test_a_redefinition_of_a_defs_name_is_a_collision_too(tmp_path: Path):
    pdir = _problem(tmp_path)
    text = ("namespace Problems.p\ndef ucf_bound : Nat := 4\n"
            "theorem x : True := trivial\nend Problems.p\n")
    hits = names.collisions(pdir, text, own_rel="proofs/L_x.lean")
    assert [(h.name, h.existing) for h in hits] == [
        ("Problems.p.ucf_bound", "Defs.lean")]


# ------------------------------------------------------ the two doors

def _conn(tmp_path: Path) -> sqlite3.Connection:
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done) "
        "VALUES ('p', '2026-08-29T00:00:00+00:00', 1)")
    conn.commit()
    return conn


def test_forward_commit_refuses_a_colliding_helper_and_lands_nothing(
        tmp_path: Path):
    from Tooling.pipeline import forward
    _problem(tmp_path)
    conn = _conn(tmp_path)
    attempts = tmp_path / ".attempts" / "fwd"
    attempts.mkdir(parents=True)
    (attempts / "new_brick_b.lean").write_text(_BRICK_B, encoding="utf-8")
    md, err = forward.extract_forward_metadata(_BRICK_B)
    assert md is not None, err
    with pytest.raises(names.NameCollision) as ei:
        forward.commit_forward_lemma(
            conn, problem="p", workspace=tmp_path, attempts_dir=attempts,
            metadata=md, source_filename="new_<slug>.lean")
    assert "four_packet_valid" in str(ei.value)
    landed = sorted(p.name for p in (tmp_path / "Problems" / "p" / "proofs").glob("*.lean"))
    assert landed == ["L_brick_a.lean"], "nothing new may land on a collision"
    assert conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0] == 0


def test_forward_commit_still_lands_a_brick_with_fresh_names(tmp_path: Path):
    from Tooling.pipeline import forward
    _problem(tmp_path)
    conn = _conn(tmp_path)
    attempts = tmp_path / ".attempts" / "fwd"
    attempts.mkdir(parents=True)
    fresh = _BRICK_B.replace("four_packet_family", "fp_family").replace(
        "four_packet_valid", "fp_valid")
    (attempts / "new_brick_b.lean").write_text(fresh, encoding="utf-8")
    md, _ = forward.extract_forward_metadata(fresh)
    out = forward.commit_forward_lemma(
        conn, problem="p", workspace=tmp_path, attempts_dir=attempts,
        metadata=md, source_filename="new_<slug>.lean")
    # the brick lands under the slug the metadata parser chose (its
    # first declaration) — the gate only cares that it landed
    assert (tmp_path / "Problems" / "p" / "proofs" / f"L_{md.slug}.lean").exists()
    assert out.goal_id > 0


def test_backward_placement_refuses_a_colliding_strategy_file(tmp_path: Path):
    """`_strategy_s*.lean` scratch files carry helpers too
    (`fp_trace_code` lived in `_strategy_s26227.lean`)."""
    from Tooling.pipeline import backward
    _problem(tmp_path)
    conn = _conn(tmp_path)
    dst = tmp_path / "Problems" / "p" / "proofs" / "_strategy_s1.lean"
    with pytest.raises(names.NameCollision):
        backward._place_unowned(conn, tmp_path, dst, _BRICK_B)
    assert not dst.exists()
    ok = _BRICK_B.replace("four_packet_family", "fp_family").replace(
        "four_packet_valid", "fp_valid")
    backward._place_unowned(conn, tmp_path, dst, ok)
    assert dst.exists()


# -------------------------------------------------- validate mirror

def test_validate_file_mirrors_the_name_gate(monkeypatch, tmp_path: Path):
    """The agent learns at validate time, not at commit: the collision
    rides `submission.names` and flips `commit_will_reject`."""
    import asyncio
    import json

    from Tooling.lsp import gateway as lsp_gateway
    from tests.test_lsp_gateway import _DiagBackend, _setup_validate_session
    _problem(tmp_path)
    backend = _DiagBackend(wait_raises=None, diags=[])
    ctx = _setup_validate_session(monkeypatch, tmp_path, backend)
    (tmp_path / "x.lean").write_text(_BRICK_B, encoding="utf-8")
    try:
        out = json.loads(asyncio.run(lsp_gateway.validate_file()))
    finally:
        lsp_gateway._session_ctx.reset(ctx)
        lsp_gateway._state.sessions.pop("tok-A", None)
    sub = out["submission"]["names"]
    assert sub["ok"] is False
    assert any(c["name"].endswith("four_packet_valid") for c in sub["collisions"])
    assert "proofs/L_brick_a.lean" in sub["teaching"]
    assert out["commit_will_reject"]
