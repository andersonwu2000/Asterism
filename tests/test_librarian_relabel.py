"""Phase-1 mechanical relabel (Tooling/quality/librarian/relabel.py).

Pure offline unit tests — no gateway, no build. Verifies the relabel core
ships the self-contained `keep` case and conservatively declines the rest.
"""
from __future__ import annotations

from Tooling.quality.librarian import relabel

PNS = "Problems.LinearAlgebra.jordan_normal_form"
TNS = "Library.LinearAlgebra.JordanForm.KernelChain"


def test_self_contained_keep_relabels():
    src = (
        "import Mathlib\n"
        f"import {PNS}.Defs\n"
        "\n"
        f"namespace {PNS}\n"
        "\n"
        "theorem chain_bottoms_li (M : Nat) : True := by\n"
        "  trivial\n"
        "\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS)
    assert r.ok, r.reason
    # Defs import dropped, Mathlib kept.
    assert "import Mathlib" in r.text
    assert f"import {PNS}.Defs" not in r.text
    assert "Problems." not in r.text
    # namespace + end renamed to target.
    assert f"namespace {TNS}" in r.text
    assert f"end {TNS}" in r.text
    # Body byte-for-byte intact.
    assert "theorem chain_bottoms_li (M : Nat) : True := by\n  trivial" in r.text


def test_self_namespace_qualified_ref_stripped():
    # residue_thm declares `windingNumber` under `namespace Complex`, so proofs
    # cite `Complex.windingNumber`. After migration the decl lives in TNS, so
    # the qualified self-ref must drop to the bare name — while a real
    # `Complex.exp` (not a problem symbol) is left untouched.
    src = (
        "import Mathlib\n"
        f"namespace {PNS}\n"
        "theorem foo (z : Nat) : True := by\n"
        "  have h := Complex.windingNumber z\n"
        "  have e := Complex.exp z\n"
        "  trivial\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        all_defs_syms={"windingNumber"}, local_defs={"windingNumber"},
        self_namespaces={"Complex"})
    assert r.ok, r.reason
    assert "Complex.windingNumber" not in r.text     # stripped to bare
    assert "windingNumber z" in r.text
    assert "Complex.exp z" in r.text                 # real Mathlib ref untouched


def test_self_namespace_strip_gated_on_declared_set():
    # Regression guard: without self_namespaces, a Complex.* self-ref is NOT
    # stripped — the strip fires only for namespaces the problem declared decls
    # under, so it can never capture an arbitrary Mathlib reference.
    src = (
        "import Mathlib\n"
        f"namespace {PNS}\n"
        "theorem foo (z : Nat) : True := by\n"
        "  have h := Complex.windingNumber z\n"
        "  trivial\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        all_defs_syms={"windingNumber"}, local_defs={"windingNumber"})
    assert r.ok, r.reason
    assert "Complex.windingNumber" in r.text         # not stripped (no self_ns)


def test_alias_declines():
    src = (
        "import Mathlib\n"
        f"import {PNS}.Defs\n"
        f"import {PNS}.proofs._strategy_s11000\n"
        f"namespace {PNS}\n"
        f"def inf_ker_card := @{PNS}.s11000\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS)
    assert not r.ok
    assert "alias" in r.reason


def test_problems_sibling_import_declines():
    src = (
        "import Mathlib\n"
        f"import {PNS}.proofs.L_some_sibling\n"
        f"namespace {PNS}\n"
        "theorem foo : True := by exact some_sibling\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS)
    assert not r.ok
    assert "sibling" in r.reason


def test_residual_problems_reference_declines():
    # Body cites a Problems symbol directly (no import line caught it) →
    # the residual-Problems guard must catch it.
    src = (
        "import Mathlib\n"
        f"namespace {PNS}\n"
        f"theorem foo : True := by exact {PNS}.bar\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS)
    assert not r.ok
    assert "residual" in r.reason


def test_no_namespace_declines():
    src = "import Mathlib\ntheorem foo : True := trivial\n"
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS)
    assert not r.ok
    assert "no `namespace" in r.reason


# --- sibling imports (keep_slugs-aware) ---

def test_keep_sibling_import_ok():
    src = (
        "import Mathlib\n"
        f"import {PNS}.proofs.L_helper\n"
        f"namespace {PNS}\n"
        "theorem foo : True := by exact helper_fact\n"
        f"end {PNS}\n"
    )
    HELP_MOD = "Library.LinearAlgebra.JordanForm.Helpers"
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"helper"}, sibling_modules={"helper": HELP_MOD})
    assert r.ok, r.reason
    assert "Problems." not in r.text                 # Problems import gone
    assert f"import {HELP_MOD}" in r.text            # Library import added
    assert f"open {HELP_MOD}" in r.text              # opened for bare name


def test_keep_sibling_import_lowercase_l_ok():
    # Proof files on disk use a lowercase `l_<slug>` prefix (Jordan: 121/165);
    # the keep-sibling import must be recognised case-insensitively, else the
    # edge is missed (usage_graph under-counts reachability + relabel declines
    # it as "strategy indirection"). Mirrors test_keep_sibling_import_ok with
    # a lowercase import.
    src = (
        "import Mathlib\n"
        f"import {PNS}.proofs.l_helper\n"
        f"namespace {PNS}\n"
        "theorem foo : True := by exact helper_fact\n"
        f"end {PNS}\n"
    )
    HELP_MOD = "Library.LinearAlgebra.JordanForm.Helpers"
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"helper"}, sibling_modules={"helper": HELP_MOD})
    assert r.ok, r.reason
    assert "Problems." not in r.text
    assert f"import {HELP_MOD}" in r.text
    assert f"open {HELP_MOD}" in r.text


def test_keep_sibling_no_module_declines():
    # keep sibling whose Library module isn't known yet → decline to Phase 2
    src = (
        "import Mathlib\n"
        f"import {PNS}.proofs.L_helper\n"
        f"namespace {PNS}\n"
        "theorem foo : True := by exact helper_fact\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"helper"}, sibling_modules={})
    assert not r.ok
    assert "no known Library module" in r.reason


def test_nonkeep_sibling_import_declines():
    src = (
        "import Mathlib\n"
        f"import {PNS}.proofs.L_reinvented\n"
        f"namespace {PNS}\n"
        "theorem foo : True := by exact reinvented\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"foo"})  # reinvented not in keep
    assert not r.ok
    assert "non-keep sibling" in r.reason


# --- alias inlining ---

def test_inline_alias_renames_strategy_to_slug():
    alias = (
        "import Mathlib\n"
        f"import {PNS}.Defs\n"
        f"import {PNS}.proofs._strategy_s11000\n"
        f"namespace {PNS}\n"
        f"def inf_ker_card := @{PNS}.s11000\n"
        f"end {PNS}\n"
    )
    strategy = (
        "import Mathlib\n"
        f"import {PNS}.Defs\n"
        f"import {PNS}.proofs.L_bridge\n"
        f"namespace {PNS}\n"
        "theorem s11000 (N : Nat) : True := by\n"
        "  exact bridge_fact\n"
        f"end {PNS}\n"
    )
    BRIDGE_MOD = "Library.LinearAlgebra.JordanForm.Bridge"
    r = relabel.inline_alias(
        alias, strategy, slug="inf_ker_card",
        problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"bridge", "inf_ker_card"},
        sibling_modules={"bridge": BRIDGE_MOD})
    assert r.ok, r.reason
    assert "theorem inf_ker_card" in r.text   # s11000 renamed to slug
    assert "s11000" not in r.text
    assert "Problems." not in r.text
    assert f"import {BRIDGE_MOD}" in r.text    # sibling Library import added
    assert f"open {BRIDGE_MOD}" in r.text
    assert f"namespace {TNS}" in r.text


def test_defs_symbol_readds_library_import():
    src = (
        "import Mathlib\n"
        f"import {PNS}.Defs\n"
        f"namespace {PNS}\n"
        "theorem foo (M : Nat) (h : IsJordanForm M) : IsJordanForm M := by\n"
        "  unfold IsJordanForm at *\n"
        "  exact h\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        defs_imports={"IsJordanForm": "Library.LinearAlgebra.JordanForm.Defs"})
    assert r.ok, r.reason
    # Problems Defs import dropped, Library Defs import added.
    assert f"import {PNS}.Defs" not in r.text
    assert "import Library.LinearAlgebra.JordanForm.Defs" in r.text
    # A migrated Defs decl lives in a SIBLING namespace, not an ancestor, so the
    # bare name `IsJordanForm` only resolves with an `open` (import alone leaves
    # it `?m`). Defs is now handled exactly like a cross-file sibling.
    assert "open Library.LinearAlgebra.JordanForm.Defs" in r.text
    # added right after import Mathlib, before namespace
    assert r.text.index("import Library.LinearAlgebra.JordanForm.Defs") \
        < r.text.index(f"namespace {TNS}")


def test_unmapped_defs_symbol_declines():
    src = (
        "import Mathlib\n"
        f"import {PNS}.Defs\n"
        f"namespace {PNS}\n"
        "theorem foo (M : Nat) (h : IsJordanForm M) : True := trivial\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        defs_imports={}, all_defs_syms={"IsJordanForm"})  # used but not migrated
    assert not r.ok
    assert "IsJordanForm" in r.reason and "no migrated" in r.reason


def test_same_file_defs_symbol_ok():
    # A Defs symbol classify co-located in THIS file (migrated together) lands
    # in this module's namespace — bare name visible, no import, no "not yet
    # migrated" decline. Without `local_defs` this wrongly declined whenever
    # classify grouped a Defs decl with a lemma that uses it (nondeterministic).
    src = (
        "import Mathlib\n"
        f"import {PNS}.Defs\n"
        f"namespace {PNS}\n"
        "theorem foo (M : Nat) (h : IsJordanForm M) : True := trivial\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        defs_imports={},                      # IsJordanForm not migrated yet
        all_defs_syms={"IsJordanForm"},
        local_defs={"IsJordanForm"})          # but co-located in THIS file
    assert r.ok, r.reason
    assert f"import {PNS}.Defs" not in r.text     # Problems Defs import dropped
    assert "IsJordanForm" in r.text               # bare name kept (same namespace)


def test_qualified_self_ref_to_known_symbol_stripped():
    # A statement citing a fully-qualified SELF ref to a KNOWN symbol (a Defs
    # decl / keep sibling, whose module is opened) is stripped to the bare name
    # — not left as a residual `Problems.` decline. This is what lets the root
    # theorem, whose Defs-shaped statement names `Problems.<p>.IsJordanForm`,
    # migrate. An unknown symbol stays qualified (caught by the residual check —
    # see test_residual_problems_reference_declines).
    src = (
        "import Mathlib\n"
        f"import {PNS}.Defs\n"
        f"namespace {PNS}\n"
        f"theorem foo (M : Nat) : {PNS}.IsJordanForm M := by sorry\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        defs_imports={"IsJordanForm": "Library.LinearAlgebra.JordanForm.Defs"},
        all_defs_syms={"IsJordanForm"})
    assert r.ok, r.reason
    assert "Problems." not in r.text                  # qualified self-ref stripped
    assert "open Library.LinearAlgebra.JordanForm.Defs" in r.text  # bare resolves


def test_citation_map_redirects_verbatim_merge():
    # body calls a merged sibling by bare name + args; citation_map
    # redirects it to the canonical Library name.
    src = (
        "import Mathlib\n"
        f"import {PNS}.proofs.L_gaps_for_starts\n"
        f"namespace {PNS}\n"
        "theorem foo : True := by\n"
        "  have h := gaps_for_starts S h0 p g\n"
        "  trivial\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"foo"},
        citation_map={"gaps_for_starts": "gaps_of_starts"})
    assert r.ok, r.reason
    assert "gaps_for_starts" not in r.text          # redirected
    assert "have h := gaps_of_starts S h0 p g" in r.text
    assert "Problems." not in r.text


def test_citation_map_word_boundary_safe():
    # a longer identifier containing the slug as a substring must NOT be
    # rewritten.
    src = (
        "import Mathlib\n"
        f"import {PNS}.proofs.L_gap\n"
        f"namespace {PNS}\n"
        "theorem foo : True := by\n"
        "  have h := gap x\n"
        "  have h2 := gap_extra y\n"   # gap_extra must survive
        "  trivial\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"foo"}, citation_map={"gap": "canonical_gap"})
    assert r.ok, r.reason
    assert "canonical_gap x" in r.text
    assert "gap_extra y" in r.text                  # untouched


def test_body_to_sorry_seeds_hole():
    # A decl whose body refs a non-keep sibling: body_to_sorry keeps the
    # signature and replaces the proof with `sorry` (seed a hole).
    src = (
        "import Mathlib\n"
        f"import {PNS}.proofs.L_reinvented\n"
        f"namespace {PNS}\n"
        "theorem foo (n : Nat) : n = n := by\n"
        "  exact reinvented n\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"foo"}, body_to_sorry=True)
    assert r.ok, r.reason
    assert "theorem foo (n : Nat) : n = n :=" in r.text   # signature kept
    assert "sorry" in r.text
    assert "reinvented" not in r.text                      # body (ref) gone
    assert "Problems." not in r.text


def test_strategy_import_thin_wrapper_seeds_hole():
    # A thin `theorem foo … := by exact sN args` wrapper (NOT a `def := @`
    # alias) imports its `_strategy_s*` module directly. inline_alias only
    # handles the `def := @` form, so this lands in relabel_self_contained.
    # Outside a body-hole pass it declines (real strategy indirection); in a
    # body-hole pass the body→sorry makes the strategy import dead, so it is
    # dropped and the decl seeds a clean hole for the per-decl LLM. Regression
    # for the BlockEnum.lean e2e STOP (block_enum := by exact s10915 k).
    src = (
        "import Mathlib\n"
        f"import {PNS}.proofs._strategy_s10915\n"
        f"namespace {PNS}\n"
        "theorem block_enum (r : Nat) : r = r := by\n"
        "  exact s10915 r\n"
        f"end {PNS}\n"
    )
    # body_to_sorry=False → still declines (cannot relabel mechanically).
    r0 = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS)
    assert not r0.ok
    assert "strategy indirection" in r0.reason
    # body_to_sorry=True → seeds a hole: signature kept, strategy import +
    # body dropped.
    r1 = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"block_enum"}, body_to_sorry=True)
    assert r1.ok, r1.reason
    assert "theorem block_enum (r : Nat) : r = r :=" in r1.text
    assert "sorry" in r1.text
    assert "_strategy_s10915" not in r1.text
    assert "s10915 r" not in r1.text
    assert "Problems." not in r1.text


def test_same_file_sibling_no_self_import():
    # A keep sibling whose Library module IS this file's target namespace
    # must NOT produce a self-import (the module doesn't exist standalone).
    src = (
        "import Mathlib\n"
        f"import {PNS}.proofs.L_helper\n"
        f"namespace {PNS}\n"
        "theorem foo : True := by exact helper\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"helper"}, sibling_modules={"helper": TNS})  # same module
    assert r.ok, r.reason
    assert f"import {TNS}" not in r.text     # no self-import
    assert f"open {TNS}" not in r.text       # no self-open


def test_inline_alias_nonkeep_sibling_declines():
    alias = (
        "import Mathlib\n"
        f"import {PNS}.proofs._strategy_s999\n"
        f"namespace {PNS}\n"
        f"def foo := @{PNS}.s999\n"
        f"end {PNS}\n"
    )
    strategy = (
        "import Mathlib\n"
        f"import {PNS}.proofs.L_reinvented\n"
        f"namespace {PNS}\n"
        "theorem s999 : True := by exact reinvented\n"
        f"end {PNS}\n"
    )
    r = relabel.inline_alias(
        alias, strategy, slug="foo",
        problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"foo"})
    assert not r.ok
    assert "non-keep sibling" in r.reason


def test_nested_strategy_redirects_to_sibling_lemma():
    # A proof body that cites another lemma's RAW strategy term (`s99`) instead
    # of the lemma name → redirect to the kept sibling lemma `helper`: import +
    # open its module, rename `s99` → `helper`. (BT nested-strategy fix.)
    src = (
        "import Mathlib\n"
        f"import {PNS}.proofs._strategy_s99\n"
        f"namespace {PNS}\n"
        "theorem foo : True := by exact s99\n"
        f"end {PNS}\n"
    )
    HELP = "Library.LinearAlgebra.JordanForm.Helper"
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"helper"}, sibling_modules={"helper": HELP},
        strategy_aliases={"s99": "helper"})
    assert r.ok, r.reason
    assert f"import {HELP}" in r.text and f"open {HELP}" in r.text
    assert "_strategy_s99" not in r.text          # raw strategy import dropped
    assert "exact helper" in r.text               # s99 → the lemma name
    import re as _re
    assert not _re.search(r"\bs99\b", r.text)     # no bare strategy term left


def test_transitive_strategy_slot_redirects_to_sibling_lemma():
    # A proof body cites a sibling's strategy slot `s99` as a bare identifier
    # while importing only that sibling's `L_` ALIAS (not `_strategy_s99`) — so
    # `s99` is in scope transitively and the import-driven redirect never fires.
    # The token-driven pass must still redirect `s99` → the sibling lemma and
    # carry its module. (BT cone_is_decomp → s11475 / isometry_… fix.)
    src = (
        "import Mathlib\n"
        f"import {PNS}.proofs.L_helper\n"          # the lemma alias, NOT _strategy_
        f"namespace {PNS}\n"
        "-- references s99 in a comment too\n"
        "theorem foo : True := by exact s99\n"
        f"end {PNS}\n"
    )
    HELP = "Library.LinearAlgebra.JordanForm.Helper"
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"helper"}, sibling_modules={"helper": HELP},
        strategy_aliases={"s99": "helper"})
    assert r.ok, r.reason
    assert f"import {HELP}" in r.text and f"open {HELP}" in r.text
    assert "exact helper" in r.text               # bare s99 in code → lemma name
    import re as _re
    assert not _re.search(r"\bs99\b", r.text)     # no bare strategy term left


def test_comment_only_strategy_slot_adds_no_import():
    # A strategy slot named ONLY in a comment must not pull in a spurious
    # sibling import (comments are stripped for slot detection). Here the
    # sibling lands in THIS file's namespace, so even a real code ref needs no
    # import — but a comment-only mention of a cross-file slot must stay inert.
    OTHER = "Library.LinearAlgebra.JordanForm.Other"
    src = (
        "import Mathlib\n"
        f"namespace {PNS}\n"
        "-- this proof is morally like s77 but does not use it\n"
        "theorem foo : True := by trivial\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS,
        keep_slugs={"other"}, sibling_modules={"other": OTHER},
        strategy_aliases={"s77": "other"})
    assert r.ok, r.reason
    assert f"import {OTHER}" not in r.text         # comment-only → no import


def test_external_library_import_preserved():
    """Library-as-input round-trip: a proof that CITES another problem's
    Library entry (`import Library.X` + a body reference) must survive
    relabel verbatim so the NEW problem can itself be Library-ized. The
    Library import is neither a Problems sibling nor Defs, so it passes
    through untouched, and the cross-Library reference is not stripped by
    the residual-Problems guard (which only targets the problem's own
    namespace)."""
    LIB = "Library.LinearAlgebra.SchurTriangularization.Triangularization"
    src = (
        "import Mathlib\n"
        f"import {LIB}\n"
        f"import {PNS}.Defs\n"
        f"namespace {PNS}\n"
        "theorem foo : True := by\n"
        f"  have := @{LIB}.main\n"
        "  trivial\n"
        f"end {PNS}\n"
    )
    r = relabel.relabel_self_contained(
        src, problem_namespace=PNS, target_namespace=TNS)
    assert r.ok, r.reason
    assert f"import {LIB}" in r.text            # external Library import kept
    assert f"{LIB}.main" in r.text              # cross-Library reference kept
    assert f"import {PNS}.Defs" not in r.text   # own Defs still dropped
