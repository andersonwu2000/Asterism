"""Phase 2 — Forward pipeline framework-side logic (Step 6 scaffold).

Tests extract_forward_metadata / is_decline / commit_forward_lemma.
Agent stage tests will be added when run_forward is fleshed out.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.pipeline import forward
from Tooling.state import db


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "proofs").mkdir()
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?, 1)",
        (db.now(),),
    )
    c.commit()
    return c


# ---------------------------------------------------------------------
# _forward_seed_scaffold — cold-seed for the fixed LSP target
# ---------------------------------------------------------------------

def test_forward_seed_scaffold_is_import_enriched_and_declless(
    workspace: Path,
) -> None:
    """The cold seed is import-enriched (so it elaborates standalone in the
    LSP slot for apply_edit / goal_at) but carries NO declaration — an
    un-edited seed must parse as 'no declaration found' (retryable), never a
    phantom lemma."""
    seed = forward._forward_seed_scaffold(problem="p", workspace=workspace)
    assert "import Mathlib" in seed
    assert seed.lstrip().startswith("import")
    assert "namespace Problems.p" in seed
    # No theorem/def/structure/class head → extract returns the no-decl error.
    md, err = forward.extract_forward_metadata(seed)
    assert md is None
    assert "declaration" in err
    # And the scaffold is not mistaken for a decline.
    assert forward.is_decline(seed) is False


def test_forward_seed_scaffold_adds_defs_import_when_present(
    workspace: Path,
) -> None:
    """When the problem ships a Defs.lean, the seed imports it too (mirrors
    the commit path's _ensure_imports_subgoal)."""
    (workspace / "Problems" / "p" / "Defs.lean").write_text(
        "import Mathlib\n", encoding="utf-8")
    seed = forward._forward_seed_scaffold(problem="p", workspace=workspace)
    assert "import Problems.p.Defs" in seed


# ---------------------------------------------------------------------
# extract_forward_metadata
# ---------------------------------------------------------------------

_NEW_LEAN_OK = """\
namespace Problems.p

-- Forward rationale: bridges Mathlib's smooth-curve formulation to
-- the piecewise case needed for residue-style contour integrals.
-- entry_kind: Backward
theorem contour_deformation_piecewise (γ : ℝ → ℂ) : True := by sorry

end Problems.p
"""

_NEW_LEAN_BUILDER_ENTRY = """\
-- Forward rationale: trivial identity needed for upstream rewrite.
-- entry_kind: Builder
theorem trivial_lemma : True := by sorry
"""

_NEW_LEAN_SORRY_FREE = """\
-- Forward rationale: closed by trivial.
-- entry_kind: Builder
theorem trivial_lemma : True := by trivial
"""

_NEW_LEAN_NO_RATIONALE = """\
-- entry_kind: Backward
theorem foo : True := by sorry
"""

_NEW_LEAN_BAD_SLUG = """\
-- Forward rationale: x
theorem Foo_Bar : True := by sorry
"""


def test_extract_metadata_happy_path() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_OK)
    assert err == ""
    assert md.slug == "contour_deformation_piecewise"
    assert "bridges Mathlib" in md.rationale
    assert md.entry_kind == "Backward"
    assert md.sorry_free is False


def test_extract_metadata_accepts_noncomputable_def() -> None:
    """`noncomputable def` (valid Lean — honest Mathlib data constructions
    need it) parses as kind='def', NOT rejected as 'no lemma' for the keyword
    sitting off column 0 (agent_feedback green_theorem #103)."""
    text = ("-- Forward rationale: build the disk rotation map.\n"
            "noncomputable def disk_rotation (x : ℝ) : ℝ := x\n")
    md, err = forward.extract_forward_metadata(text)
    assert err == ""
    assert md is not None and md.kind == "def" and md.slug == "disk_rotation"


def test_extract_metadata_attribute_before_decl() -> None:
    """A leading `@[simp]` attribute is tolerated; kind/slug still parse."""
    text = ("-- Forward rationale: x.\n"
            "@[simp] theorem foo_bar : True := by sorry\n")
    md, err = forward.extract_forward_metadata(text)
    assert err == "" and md is not None and md.slug == "foo_bar"


def test_extract_metadata_modifier_does_not_relax_slug() -> None:
    """Tolerating `noncomputable` must NOT relax the snake_case slug rule —
    a camelCase def name is still rejected (agent_feedback #69)."""
    text = ("-- Forward rationale: x.\n"
            "noncomputable def diskRotation : ℝ := 0\n")
    md, err = forward.extract_forward_metadata(text)
    assert md is None and "must match" in err


def test_extract_metadata_builder_entry() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_BUILDER_ENTRY)
    assert err == ""
    assert md.entry_kind == "Builder"


def test_extract_metadata_sorry_free() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_SORRY_FREE)
    assert err == ""
    assert md.sorry_free is True


def test_extract_metadata_missing_rationale() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_NO_RATIONALE)
    assert md is None
    assert "rationale" in err.lower()


def test_extract_metadata_bad_slug() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_BAD_SLUG)
    assert md is None
    assert "slug" in err.lower()


def test_extract_metadata_no_theorem() -> None:
    text = "import Mathlib\nnamespace Problems.p\nend Problems.p\n"
    md, err = forward.extract_forward_metadata(text)
    assert md is None
    assert "theorem" in err.lower()


# ---------------------------------------------------------------------
# is_decline
# ---------------------------------------------------------------------

def test_is_decline_recognized() -> None:
    text = (
        "-- decline: library_sufficient\n"
        "-- ## Why\n"
        "-- Brief asked for X; existing covers it.\n"
        "theorem _forward_decline : True := by trivial\n"
    )
    assert forward.is_decline(text) is True


def test_is_decline_not_matched_on_normal_file() -> None:
    assert forward.is_decline(_NEW_LEAN_OK) is False


def test_extract_decline_why_pulls_reasoning() -> None:
    """#4 — the agent's `## Why` block is extracted (comment markers
    stripped, multi-line joined) so it can be surfaced to the Strategist."""
    text = (
        "namespace Problems.p\n"
        "-- decline: library_sufficient\n"
        "-- ## Why\n"
        "-- Brief asked for foo_bridge; Mathlib's `extDerivWithin_apply`\n"
        "-- already covers it, composed with `Finset.sum_congr`.\n"
        "theorem _forward_decline : True := by trivial\n"
        "end Problems.p\n"
    )
    why = forward._extract_decline_why(text)
    assert "extDerivWithin_apply" in why
    assert "Finset.sum_congr" in why
    assert "--" not in why          # comment markers stripped
    assert "theorem" not in why     # stops at the decl


def test_extract_decline_why_absent_returns_empty() -> None:
    assert forward._extract_decline_why(
        "-- decline: library_sufficient\ntheorem _x : True := by trivial\n"
    ) == ""


# ---------------------------------------------------------------------
# commit_forward_lemma
# ---------------------------------------------------------------------

def test_auto_prepend_candidate_imports_adds_mathlib_and_defs(
    workspace: Path,
) -> None:
    """SG 2026-05-18 regression: `forward.md` tells agents not to write
    imports, but framework's commit-side verify_file reads the file
    as-is. Without auto-prepend, bare statements fail to elaborate
    (e.g. `HSub ℝ ℝ` instance-resolution error). Mutate src so verify
    AND commit both see the enriched body."""
    pdir = workspace / "Problems" / "p"
    (pdir / "Defs.lean").write_text(
        "import Mathlib\nopen Real\n\nnamespace Problems.p\n"
        "def Foo : Type := Unit\n\nend Problems.p\n",
        encoding="utf-8",
    )
    attempts = workspace / ".attempts" / "fwd-imports"
    attempts.mkdir(parents=True)
    src = attempts / "new_bare.lean"
    src.write_text(
        "namespace Problems.p\n\n"
        "-- Forward rationale: just check the import path\n"
        "-- entry_kind: Backward\n"
        "theorem bare (a b : ℝ) : a - b = a - b := by sorry\n\n"
        "end Problems.p\n",
        encoding="utf-8",
    )

    enriched = forward._auto_prepend_candidate_imports(
        src, problem="p", workspace=workspace,
    )

    on_disk = src.read_text(encoding="utf-8")
    assert on_disk == enriched, "src must be mutated on disk"
    assert "import Mathlib" in on_disk
    assert "import Problems.p.Defs" in on_disk
    assert "open Real" in on_disk
    # Original body preserved (not overwritten).
    assert "theorem bare (a b : ℝ)" in on_disk


def test_auto_prepend_candidate_imports_idempotent(
    workspace: Path,
) -> None:
    """Re-running on already-enriched content is a no-op — agents who
    DID write the imports themselves don't get duplicate lines."""
    pdir = workspace / "Problems" / "p"
    (pdir / "Defs.lean").write_text(
        "import Mathlib\n\nnamespace Problems.p\n\nend Problems.p\n",
        encoding="utf-8",
    )
    attempts = workspace / ".attempts" / "fwd-idem"
    attempts.mkdir(parents=True)
    src = attempts / "new_x.lean"
    pre_body = (
        "import Mathlib\nimport Problems.p.Defs\n\n"
        "namespace Problems.p\n\n"
        "-- Forward rationale: pre-imported\n"
        "-- entry_kind: Backward\n"
        "theorem x : True := by trivial\n\n"
        "end Problems.p\n"
    )
    src.write_text(pre_body, encoding="utf-8")

    enriched = forward._auto_prepend_candidate_imports(
        src, problem="p", workspace=workspace,
    )

    assert enriched == pre_body
    assert src.read_text(encoding="utf-8") == pre_body


def test_commit_writes_lean_file_and_inserts_goal(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    attempts = workspace / ".attempts" / "fwd-1"
    attempts.mkdir(parents=True)
    (attempts / "new_contour_deformation_piecewise.lean").write_text(
        _NEW_LEAN_OK, encoding="utf-8")

    md, _ = forward.extract_forward_metadata(_NEW_LEAN_OK)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )

    dest = workspace / "Problems" / "p" / "proofs" / \
        "L_contour_deformation_piecewise.lean"
    assert dest.exists()
    # The consumed `-- entry_kind:` directive (parsed into the DB column below)
    # must NOT persist into the permanent proof file — the Forward strip gap.
    assert "-- entry_kind:" not in dest.read_text(encoding="utf-8")
    g = db.get_goal(conn, outcome.goal_id)
    assert g["origin"] == "forward"
    assert g["entry_kind"] == "Backward"
    assert g["status"] == "open"


def test_commit_statement_prefers_oracle_conclusion(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """decl-#1: when the caller threads the candidate elaboration's
    decl_info, goals.statement is the kernel-true pp conclusion (canonical
    form), not the text extraction."""
    attempts = workspace / ".attempts" / "fwd-oracle"
    attempts.mkdir(parents=True)
    (attempts / "new_contour_deformation_piecewise.lean").write_text(
        _NEW_LEAN_OK, encoding="utf-8")
    r = {"startLine": 1, "startCol": 0, "endLine": 1, "endCol": 40}
    sel = {"startLine": 1, "startCol": 8, "endLine": 1, "endCol": 9}
    info = {
        "commands": [{"kind": "Lean.Parser.Command.declaration",
                      "range": r, "declNames": []}],
        "decls": [{
            "fqName": "Problems.p.contour_deformation_piecewise",
            "userName": "Problems.p.contour_deformation_piecewise",
            "kind": "thm", "isProp": True, "isNoncomputable": False,
            "isProtected": False, "isPrivate": False, "isInstance": False,
            "signature": ("Problems.p.contour_deformation_piecewise "
                          "(γ : ℝ → ℂ) : True"),
            "docstring": None, "cmdIdx": 0, "range": r, "selection": sel,
        }],
    }

    md, _ = forward.extract_forward_metadata(_NEW_LEAN_OK)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean", decl_info=info,
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert g["statement"] == "True"


def test_commit_statement_text_fallback_without_decl_info(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """No decl_info (old gateway / stub verifier) → the historical text
    extraction still mints the statement."""
    attempts = workspace / ".attempts" / "fwd-fallback"
    attempts.mkdir(parents=True)
    (attempts / "new_contour_deformation_piecewise.lean").write_text(
        _NEW_LEAN_OK, encoding="utf-8")
    md, _ = forward.extract_forward_metadata(_NEW_LEAN_OK)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert "True" in g["statement"]        # text form keeps binders too
    assert "γ" in g["statement"]


def test_commit_sorry_free_marks_goal_proved(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    attempts = workspace / ".attempts" / "fwd-2"
    attempts.mkdir(parents=True)
    (attempts / "new_trivial_lemma.lean").write_text(
        _NEW_LEAN_SORRY_FREE, encoding="utf-8")

    md, _ = forward.extract_forward_metadata(_NEW_LEAN_SORRY_FREE)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert g["status"] == "proved"


def test_commit_sorry_free_fails_axiom_gate(
    workspace: Path, conn: sqlite3.Connection,
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    """A literally-sorry-free Forward decl whose PROOF TERM depends on
    `sorryAx` (a transitive/cited sorry a `\\bsorry\\b` scan can't see) must
    NOT be marked proved — the axiom gate fails the commit, removes the
    placed file, and raises ForwardAxiomViolation (run_forward → failed)."""
    from Tooling.pipeline import _axiom
    attempts = workspace / ".attempts" / "fwd-gate"
    attempts.mkdir(parents=True)
    (attempts / "new_trivial_lemma.lean").write_text(
        _NEW_LEAN_SORRY_FREE, encoding="utf-8")
    md, _ = forward.extract_forward_metadata(_NEW_LEAN_SORRY_FREE)

    monkeypatch.setattr(_axiom, "axiom_gate", lambda *a, **k: _axiom.AxiomGateResult(
        False, "axiom_violation", "proof term depends on sorryAx"))

    with pytest.raises(forward.ForwardAxiomViolation) as ei:
        forward.commit_forward_lemma(
            conn, problem="p", workspace=workspace,
            attempts_dir=attempts, metadata=md,
            source_filename="new_<slug>.lean",
        )
    assert ei.value.failure_reason == "axiom_violation"
    # No goal created, placed file removed (no fake-proved artifact left).
    assert db.goal_by_slug(conn, "p", md.slug) is None
    assert not (workspace / "Problems" / "p" / "proofs"
                / f"L_{md.slug}.lean").exists()


def test_commit_collision_raises(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    # Pre-existing file at the target path
    proofs = workspace / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True, exist_ok=True)
    (proofs / "L_contour_deformation_piecewise.lean").write_text(
        "preexisting\n", encoding="utf-8")

    attempts = workspace / ".attempts" / "fwd-3"
    attempts.mkdir(parents=True)
    (attempts / "new_contour_deformation_piecewise.lean").write_text(
        _NEW_LEAN_OK, encoding="utf-8")

    md, _ = forward.extract_forward_metadata(_NEW_LEAN_OK)
    with pytest.raises(FileExistsError):
        forward.commit_forward_lemma(
            conn, problem="p", workspace=workspace,
            attempts_dir=attempts, metadata=md,
            source_filename="new_<slug>.lean",
        )


# ---------------------------------------------------------------------
# Phase 4 — Forward produces def / structure / class
# ---------------------------------------------------------------------

_NEW_LEAN_DEF = """\
namespace Problems.p

-- Forward rationale: scaffolding `lineThrough` predicate referenced by
-- the planned perpendicular-distance chain. No proof obligation.
def line_through (q r : ℝ × ℝ) : Set (ℝ × ℝ) := { p | True }

end Problems.p
"""

_NEW_LEAN_STRUCTURE = """\
namespace Problems.p

-- Forward rationale: bundle (foot, distance) so downstream lemmas can
-- pass a single record instead of two parallel arguments.
structure perp_data where
  foot : ℝ × ℝ
  dist : ℝ

end Problems.p
"""

_NEW_LEAN_CLASS = """\
namespace Problems.p

-- Forward rationale: typeclass abstraction over the determinant test
-- so future variants can plug in alternative collinearity oracles.
class collinear_oracle (α : Type) where
  test : α → α → α → Prop

end Problems.p
"""


def test_extract_metadata_def_kind() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_DEF)
    assert err == ""
    assert md.kind == "def"
    assert md.slug == "line_through"
    # entry_kind is irrelevant for non-theorem kinds; default kept for
    # NOT NULL column compatibility.
    assert md.entry_kind == "Backward"


def test_extract_metadata_structure_kind() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_STRUCTURE)
    assert err == ""
    assert md.kind == "structure"
    assert md.slug == "perp_data"


def test_extract_metadata_class_kind() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_CLASS)
    assert err == ""
    assert md.kind == "class"
    assert md.slug == "collinear_oracle"


_NEW_LEAN_INDUCTIVE = """\
namespace Problems.p

-- Forward rationale: derivation trees for the toy proof system so the
-- soundness claim can recurse over constructors.
inductive derivation (α : Type) : ℕ → Type where
  | ax : α → derivation α 0
  | mp : derivation α 0 → derivation α 1

end Problems.p
"""

_NEW_LEAN_INDUCTIVE_SORRY = """\
namespace Problems.p

-- Forward rationale: placeholder constructor type left open.
inductive bad_tree where
  | leaf : sorry → bad_tree

end Problems.p
"""


def test_extract_metadata_inductive_kind() -> None:
    md, err = forward.extract_forward_metadata(_NEW_LEAN_INDUCTIVE)
    assert err == ""
    assert md.kind == "inductive"
    assert md.slug == "derivation"
    assert md.sorry_free


def test_extract_metadata_inductive_rejects_sorry() -> None:
    """v19: an inductive has no proof body to fill later — a sorry can
    only sit inside a constructor type, which no dispatch path repairs.
    Parse-level reject → fast agent retry."""
    md, err = forward.extract_forward_metadata(_NEW_LEAN_INDUCTIVE_SORRY)
    assert md is None
    assert "inductive" in err and "sorry" in err


def test_extract_statement_string_inductive_keeps_binders() -> None:
    """Nominal kinds mint `<binders> : <conclusion>` (up to `where`), not
    the bare universe — a `Type`-only key would de-discriminate the
    statement dedupe pre-filter (5065/5026, inverted)."""
    s = forward._extract_statement_string(
        _NEW_LEAN_INDUCTIVE, "derivation", "inductive")
    assert s is not None
    assert "(α : Type)" in s and "ℕ → Type" in s
    assert "where" not in s and "| ax" not in s


_NEW_LEAN_INSTANCE = """\
namespace Problems.p

-- Forward rationale: register the toy depth interface for formulas so
-- downstream claims can use typeclass resolution.
instance formula_depth : has_toy_depth prop_formula where
  depth := fun _ => 1

end Problems.p
"""

_NEW_LEAN_INSTANCE_TERM = """\
namespace Problems.p

-- Forward rationale: same instance, term-mode body.
noncomputable instance formula_depth : has_toy_depth prop_formula :=
  ⟨fun _ => 1⟩

end Problems.p
"""

_NEW_LEAN_INSTANCE_ANON = """\
namespace Problems.p

-- Forward rationale: idiomatic anonymous instance (must be rejected).
instance : has_toy_depth prop_formula where
  depth := fun _ => 1

end Problems.p
"""


def test_extract_metadata_instance_kind() -> None:
    for src in (_NEW_LEAN_INSTANCE, _NEW_LEAN_INSTANCE_TERM):
        md, err = forward.extract_forward_metadata(src)
        assert err == ""
        assert md.kind == "instance"
        assert md.slug == "formula_depth"


def test_extract_metadata_anonymous_instance_targeted_error() -> None:
    """v20: the chain is name-keyed — an anonymous `instance` gets a
    targeted retry message, not the generic no-declaration error."""
    md, err = forward.extract_forward_metadata(_NEW_LEAN_INSTANCE_ANON)
    assert md is None
    assert "anonymous" in err and "instance <slug>" in err


def test_extract_statement_string_bare_nominal_head_returns_none() -> None:
    """`structure foo where` has nothing between name and `where`; the
    old one-char-minimum lazy group swallowed the fields block up to
    end-of-string (toy_pair 2026-07-05). Bare head → None; the commit
    mint then falls back to the oracle conclusion."""
    src = "structure toy_pair where\n  a : ℕ\n  b : ℕ\n\nend P\n"
    assert forward._extract_statement_string(
        src, "toy_pair", "structure") is None
    # A signed head still extracts as before.
    assert forward._extract_statement_string(
        "structure toy_model : Type 1 where\n  val : ℕ → Prop\n",
        "toy_model", "structure") == "Type 1"


def test_extract_statement_string_instance_both_body_forms() -> None:
    """Instance statements stop at `:=` OR `where` — the where-block's
    inner `:= …` must not swallow the class-application type."""
    for src in (_NEW_LEAN_INSTANCE, _NEW_LEAN_INSTANCE_TERM):
        s = forward._extract_statement_string(src, "formula_depth",
                                              "instance")
        assert s == "has_toy_depth prop_formula"


def test_non_theorem_kinds_in_NON_THEOREM_KINDS_constant() -> None:
    """Constant must list every non-theorem kind the parser accepts so
    dispatch / library / verify share a single source of truth."""
    assert forward.NON_THEOREM_KINDS == frozenset(
        {"def", "structure", "class", "inductive", "instance"})


def test_commit_def_marks_goal_proved_immediately(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """A concrete (sorry-free) def is a leaf artifact and commits as
    status='proved' directly, bypassing BFS. Curry-Howard unified: the
    same sorry-free rule applies to theorem / def / structure / class
    — the kind only changes the universe (Prop vs Type) of the
    inhabitant being constructed."""
    attempts = workspace / ".attempts" / "fwd-def"
    attempts.mkdir(parents=True)
    (attempts / "new_line_through.lean").write_text(_NEW_LEAN_DEF,
                                                    encoding="utf-8")
    md, _ = forward.extract_forward_metadata(_NEW_LEAN_DEF)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert g["kind"] == "def"
    assert g["status"] == "proved"
    assert g["origin"] == "forward"


def test_commit_structure_marks_goal_proved_immediately(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    attempts = workspace / ".attempts" / "fwd-struct"
    attempts.mkdir(parents=True)
    (attempts / "new_perp_data.lean").write_text(_NEW_LEAN_STRUCTURE,
                                                 encoding="utf-8")
    md, _ = forward.extract_forward_metadata(_NEW_LEAN_STRUCTURE)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert g["kind"] == "structure"
    assert g["status"] == "proved"


def test_commit_class_marks_goal_proved_immediately(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    attempts = workspace / ".attempts" / "fwd-class"
    attempts.mkdir(parents=True)
    (attempts / "new_collinear_oracle.lean").write_text(_NEW_LEAN_CLASS,
                                                        encoding="utf-8")
    md, _ = forward.extract_forward_metadata(_NEW_LEAN_CLASS)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert g["kind"] == "class"
    assert g["status"] == "proved"


_NEW_LEAN_DEF_WITH_SORRY = """\
namespace Problems.p

-- Forward rationale: stub for the singular-chain boundary operator;
-- a real value will land in a follow-up.
def singular_chain_boundary (n : Nat) : Nat := sorry

end Problems.p
"""


def test_commit_def_with_sorry_enters_bfs_as_open(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Curry-Howard unified — a `def := sorry` is a deferred Type-valued
    inhabitant request, semantically the same shape as `theorem := by
    sorry`. Pre-unification framework rubber-stamped it as 'proved'
    and downstream lemmas about its value hit an unprovable wall
    (brouwer 2026-05-22 G3: g2767 `singular_chain_boundary` fake-
    proved → downstream g2771 stuck). Post-fix the goal lands at
    status='open' + detached=1 and enters BFS like any sorry-bearing
    theorem."""
    attempts = workspace / ".attempts" / "fwd-def-sorry"
    attempts.mkdir(parents=True)
    (attempts / "new_singular_chain_boundary.lean").write_text(
        _NEW_LEAN_DEF_WITH_SORRY, encoding="utf-8")
    md, _ = forward.extract_forward_metadata(_NEW_LEAN_DEF_WITH_SORRY)
    assert md.kind == "def"
    assert md.sorry_free is False
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert g["kind"] == "def"
    assert g["status"] == "open"
    assert g["detached"] == 1
    # And it must surface via db.open_goals so dispatch picks it up.
    open_ids = {int(r["id"]) for r in db.open_goals(conn)}
    assert outcome.goal_id in open_ids


def test_open_goals_returns_non_theorem_kinds(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Curry-Howard unified — a def / structure / class goal at
    status='open' (i.e. shipped with a sorry-bearing body) must enter
    BFS so Backward / Builder can attack it. Pre-unification the SQL
    filter `g.kind = 'theorem'` silently stranded these; brouwer
    2026-05-22 G3 incident."""
    db.insert_goal(
        conn, problem="p", slug="main", lean_path="P/main.lean",
        statement="T", origin="root", depth=0, kind="theorem",
    )
    def_open = db.insert_goal(
        conn, problem="p", slug="deferred_def",
        lean_path="P/proofs/L_deferred_def.lean", statement="def sig",
        origin="forward", depth=0, kind="def",
    )
    db.set_goal_detached(conn, def_open, True)
    theorem_open = db.insert_goal(
        conn, problem="p", slug="deferred_theorem",
        lean_path="P/proofs/L_deferred_theorem.lean", statement="T",
        origin="forward", depth=0, kind="theorem",
    )
    db.set_goal_detached(conn, theorem_open, True)
    open_ids = {int(r["id"]) for r in db.open_goals(conn)}
    assert def_open in open_ids
    assert theorem_open in open_ids


def test_commit_marks_forward_goal_detached(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Regression — Forward output goals must be `detached=1` so BFS
    picks them up. `db.open_goals` alive CTE seeds = root ∪ detached
    ∪ strategy descendants; Forward goals have NO parent strategy edge,
    so without detached=1 a sorry-bearing Forward (status='open') is
    invisible to BFS forever (silent stuck). SG 2026-05-18 take 7
    trace: goal 1676 'kelly_step_inward_kernel' sat at open/detached=0
    while bfs_refill silently skipped it; daemon idle-progressed
    against root without ever closing the Forward sorry."""
    # Sorry-bearing Forward — needs Backward attack
    attempts = workspace / ".attempts" / "fwd-detach-open"
    attempts.mkdir(parents=True)
    (attempts / "new_contour_deformation_piecewise.lean").write_text(
        _NEW_LEAN_OK, encoding="utf-8")
    md, _ = forward.extract_forward_metadata(_NEW_LEAN_OK)
    outcome = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts, metadata=md,
        source_filename="new_<slug>.lean",
    )
    g = db.get_goal(conn, outcome.goal_id)
    assert g["status"] == "open"
    assert g["detached"] == 1
    # And it now appears in open_goals (BFS dispatch source).
    open_ids = {int(r["id"]) for r in db.open_goals(conn)}
    assert outcome.goal_id in open_ids

    # Sorry-free Forward — proved at commit. detached still set
    # defensively; open_goals filters by status so it doesn't surface.
    attempts2 = workspace / ".attempts" / "fwd-detach-proved"
    attempts2.mkdir(parents=True)
    (attempts2 / "new_trivial_lemma.lean").write_text(
        _NEW_LEAN_SORRY_FREE, encoding="utf-8")
    md2, _ = forward.extract_forward_metadata(_NEW_LEAN_SORRY_FREE)
    outcome2 = forward.commit_forward_lemma(
        conn, problem="p", workspace=workspace,
        attempts_dir=attempts2, metadata=md2,
        source_filename="new_<slug>.lean",
    )
    g2 = db.get_goal(conn, outcome2.goal_id)
    assert g2["status"] == "proved"
    assert g2["detached"] == 1


def test_extract_metadata_no_declaration_lists_all_kinds() -> None:
    """Error message must mention all 4 accepted kinds so the agent
    knows what to write when it omits the declaration head."""
    md, err = forward.extract_forward_metadata(
        "-- Forward rationale: empty body\nnamespace Problems.p\nend Problems.p\n"
    )
    assert md is None
    for kw in ("theorem", "def", "structure", "class"):
        assert kw in err
