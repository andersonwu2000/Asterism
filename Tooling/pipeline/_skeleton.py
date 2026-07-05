"""Skeleton-driven strategy patch helpers + def-alias promotion.

Extracted from `pipeline/__init__.py`. Pure module: shared helpers
for Backward (skeleton + import injection) and Verify (promote +
rollback).
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from ._lake import lean_path_to_module
from ..quality.dedupe import leading_decl_attrs


# Curry-Howard unified — the prove loop accepts any declaration head
# whose body is `:= by sorry`-shaped (theorem / def / structure / class).
# The keyword is captured so `build_strategy_skeleton` can preserve it
# in the rewritten skeleton; Lean's elaborator picks the same form for
# the strategy patch as the parent stub. Shared SoT: state.assemble
# (the gateway's locked-signature submission mirror runs the same
# comparison — task #5 D-lite).
from ..state.assemble import (  # noqa: E402
    DECL_KIND_RE_SRC as _DECL_HEAD_RE,
    normalize_signature,
    signature_prefix,
)
_DECL_MODIFIERS_RE = r"(?:noncomputable|private|protected|partial|unsafe)"


def leading_decl_modifiers(text: str, slug: str) -> str:
    """Keyword modifiers (`noncomputable` / `private` / …) immediately preceding
    the `<kind> <slug>` declaration in `text`, normalized to single spaces with
    a trailing space, or '' if none.

    Distinct from `leading_decl_attrs` (which carries only `@[...]` attribute
    blocks): a data goal's parent stub is `noncomputable def <slug> …`, and
    `signature_prefix` starts the copy AT the keyword — dropping the modifier.
    The renamed skeleton `def s<id> … := by sorry` then compile-fails with
    "mark it 'noncomputable'" (agent_feedback green_theorem #77/#78). Re-prepend
    the modifier so a data-valued goal's skeleton keeps the keyword it needs."""
    m = re.search(
        r"((?:" + _DECL_MODIFIERS_RE + r"\s+)+)"
        + r"(?:theorem|def|structure|class)\s+" + re.escape(slug) + r"\b",
        text,
    )
    if not m:
        return ""
    return " ".join(m.group(1).split()) + " "


def _has_top_level_type_colon(sig: str, name: str) -> bool:
    """True iff `sig` contains a top-level `:` (i.e. a type colon
    between the binders and the body), excluding any `:` nested inside
    binder groups `( ... )` / `{ ... }` / `[ ... ]`.

    Walks after the declaration head `<kind> <name>` so a stray `:`
    inside `<kind>` itself can't false-positive.
    """
    m = re.search(_DECL_HEAD_RE + re.escape(name) + r"\b", sig)
    if not m:
        return False
    pos = m.end()
    depth = 0
    n = len(sig)
    while pos < n:
        ch = sig[pos]
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth = max(0, depth - 1)
        elif depth == 0 and ch == ":":
            return True
        pos += 1
    return False


def build_strategy_skeleton(
    parent_text: str, *, parent_slug: str, sid_token: str,
    namespace: str, oracle_sig: str | None = None,
) -> str | None:
    """Construct a strategy patch skeleton by copying the parent stub's
    `<kind> <parent_slug> ...` declaration verbatim, then renaming the
    declaration to `<sid_token>` and stubbing the body as `by sorry`.

    `<kind>` ∈ {theorem, def, structure, class} — the parent's keyword
    is preserved so the elaborator sees a matching declaration head
    (a `def`-parent's strategy patch stays a `def`, not a `theorem`).

    Returns None if no matching declaration head is found, or if the
    matched head has no top-level type colon AND no `oracle_sig` was
    supplied. The colon-less case catches promoted-alias parents
    (`def g := @ns.sN`, no `:` between name and `:=`) and inferred-type
    defs (`def g (x : A) := body`): Backward's signature lock requires
    a typed signature to be meaningful. For the LATTER, `oracle_sig`
    (the decl's ppSignature — the elaborator's rendering, type always
    explicit) reconstructs the head the source doesn't spell (decl-#2,
    sphere g4946: 5/5 attempts burned on `parent_stub_not_decomposable`).
    The caller decides when to pass it (sorry-bearing stubs only —
    a promoted-alias parent means the goal is proved and must keep
    aborting cleanly).
    """
    sig = signature_prefix(parent_text, parent_slug)
    if not sig or not _has_top_level_type_colon(sig, parent_slug):
        return _skeleton_from_oracle_sig(
            parent_text, parent_slug=parent_slug, sid_token=sid_token,
            namespace=namespace, oracle_sig=oracle_sig)
    new_sig = re.sub(
        _DECL_HEAD_RE + re.escape(parent_slug) + r"\b",
        lambda m: f"{m.group(1)} {sid_token}", sig, count=1,
    )
    # Re-prepend the parent's keyword modifiers (`noncomputable` …) that
    # `signature_prefix` dropped — a data-valued `def` goal needs them or the
    # stub fails to compile (see `leading_decl_modifiers`).
    mods = leading_decl_modifiers(parent_text, parent_slug)
    imports = [ln for ln in parent_text.splitlines()
               if ln.strip().startswith("import")]
    if not imports:
        imports = ["import Mathlib"]
    # Carry the goal's own `open` header verbatim. `parent_text` is the
    # goal's canonical file (proofs/L_<slug>.lean or Root.lean), so its
    # opens are exactly the namespaces the signature elaborates against
    # — `open scoped Manifold` for `𝓡∂`, `open MeasureTheory` for
    # `volume` / `Integrable`, problem `open Library.*` for custom defs.
    # Omitting them seeded a skeleton that elaborated with misleading
    # `unexpected token '∂'` / autoImplicit errors, costing every Backward
    # spawn a round-trip to reconstruct the header from a sibling proof
    # (agent_feedback T2, ~8 reports). Copying the goal's OWN opens (not a
    # shared problem template) brings only what this goal needs, so
    # pure-analysis sub-goals stay cargo-free.
    opens = [ln for ln in parent_text.splitlines()
             if ln.strip().startswith("open ")]
    # Carry the goal's file-level `variable {...}` binders too. A signature
    # copied from the parent often relies on auto-bound `variable` binders
    # (`variable {M : Type*} [TopologicalSpace M] …` for a manifold goal)
    # rather than spelling them in the head; without them the skeleton
    # elaborates with `unknown identifier` / autoImplicit errors on the binder
    # names, costing a Backward round-trip to reconstruct the preamble from a
    # sibling (agent_feedback T13, seed-skeleton defects). `variable` only
    # attaches binders the decl actually references, so copying all of them is
    # scope-safe — unused ones are ignored. Placed inside the namespace, just
    # above the decl (mirrors the parent's own scoping).
    variables = [ln for ln in parent_text.splitlines()
                 if ln.strip().startswith("variable ")]
    header = "\n".join(imports)
    if opens:
        header += "\n" + "\n".join(opens)
    var_block = ("\n".join(variables) + "\n\n") if variables else ""
    return (
        header + "\n\n"
        f"namespace {namespace}\n\n"
        f"{var_block}"
        f"{mods}{new_sig} := by sorry\n\n"
        f"end {namespace}\n"
    )


def _skeleton_from_oracle_sig(
    parent_text: str, *, parent_slug: str, sid_token: str,
    namespace: str, oracle_sig: str | None,
) -> str | None:
    """The oracle-reconstruction arm of `build_strategy_skeleton` (decl-#2):
    the source spells no top-level type colon, but the decl's ppSignature
    makes the elaborator's inferred type explicit. Build the skeleton head
    from that instead of the source verbatim.

    Two deliberate differences from the verbatim path:
      - NO `variable` lines are carried: a ppSignature already incorporates
        the section variables the decl uses as its own binders — carrying
        the lines too would shadow them (noisy at best, instance-binder
        confusion at worst).
      - `noncomputable` comes from BOTH the source modifiers and the
        keyword the pp form implies nothing about — the caller's oracle
        decl carries env truth, but source modifiers are kept as the
        cheap union (mirrors `promote_to_alias`'s BUG4 fix direction).
    """
    if not oracle_sig:
        return None
    from ..lsp.decl_oracle import split_signature
    parts = split_signature(oracle_sig)
    if parts is None:
        return None
    _name, universes, binders_and_type = parts
    km = re.search(_DECL_HEAD_RE + re.escape(parent_slug) + r"\b",
                   parent_text)
    if km is None:
        return None                    # decl head absent — same as verbatim
    kind = km.group(1)
    mods = leading_decl_modifiers(parent_text, parent_slug)
    imports = [ln for ln in parent_text.splitlines()
               if ln.strip().startswith("import")]
    if not imports:
        imports = ["import Mathlib"]
    # Opens still matter on this path: ppSignature renders names fully
    # qualified, but SCOPED NOTATION (`𝓡∂` …) needs its `open scoped`.
    opens = [ln for ln in parent_text.splitlines()
             if ln.strip().startswith("open ")]
    header = "\n".join(imports)
    if opens:
        header += "\n" + "\n".join(opens)
    return (
        header + "\n\n"
        f"namespace {namespace}\n\n"
        f"{mods}{kind} {sid_token}{universes} {binders_and_type} "
        f":= by sorry\n\n"
        f"end {namespace}\n"
    )


def inject_imports_for_subs(
    workspace: Path, patch_path: Path,
    sub_dest_paths: list[Path],
) -> None:
    """Splice `import <module>` lines into `patch_path` for every
    sub-goal file the agent placed. Idempotent; new imports go after
    the last existing import line."""
    if not patch_path.exists() or not sub_dest_paths:
        return
    text = patch_path.read_text(encoding="utf-8")
    existing = {ln.strip() for ln in text.splitlines()
                if ln.strip().startswith("import")}
    needed = []
    for sub in sub_dest_paths:
        mod = lean_path_to_module(workspace, sub)
        line = f"import {mod}"
        if line not in existing:
            needed.append(line)
    if not needed:
        return
    lines = text.splitlines()
    insert_at = 0
    for idx, ln in enumerate(lines):
        if ln.strip().startswith("import"):
            insert_at = idx + 1
    new_lines = lines[:insert_at] + needed + lines[insert_at:]
    patch_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def verify_backup_path(parent_abs: Path, sid_token: str) -> Path:
    """Backup filename keyed by sid_token so concurrent Verifies on
    sibling strategies of the same parent goal can't clobber each
    other's backup."""
    return parent_abs.with_suffix(
        parent_abs.suffix + f".verify_backup_{sid_token}")


def promote_to_alias(
    parent_abs: Path, *,
    namespace: str, slug: str, sid_token: str,
    scratch_module: str,
    annotation: str = "",
    scratch_text: str = "",
) -> Path | None:
    """Rewrite parent stub as a re-export alias of the strategy:
        <annotation comment lines, if any>
        <orig imports + scratch_module>
        namespace <namespace>
        def <slug> := @<namespace>.<sid_token>
        end <namespace>

    `def` (not `theorem`) is required because Lean 4 syntax demands an
    explicit `: <type>` after a theorem name, and we deliberately want
    Lean to copy the type from the strategy theorem's signature at
    elaboration. This sidesteps the older bug where serializing
    `goal.statement` (just the conclusion — binders stripped during
    extraction) into a fresh `theorem ... : <stmt> := s_id` left
    identifiers like `P` unbound, triggering `Function expected ...`
    at lake build.

    `annotation` (a `--` line-comment block extracted from the winning
    strategy patch by `_extract_leading_comments`) is prepended verbatim
    if non-empty. Comments are Lean-inert, so this does not affect alias
    elaboration; it just hydrates the proved goal's source with the
    winning strategy's rationale for human readers + agent grep.

    Returns the backup path the caller should keep until the post-
    promote lake build succeeds (delete on success, restore on fail
    via `rollback_promote`). Returns None if no original file existed.
    """
    original = parent_abs.read_text(encoding="utf-8") if parent_abs.exists() else ""
    orig_imports = [ln for ln in original.splitlines()
                    if ln.strip().startswith("import")]
    if f"import {scratch_module}" not in orig_imports:
        orig_imports.append(f"import {scratch_module}")
    # BUG4 residual (sphere_homology 2026-07-04, recurred twice): the
    # modifier carry below reads the PARENT STUB — but when the stub was
    # never marked `noncomputable` and the winning strategy decl IS, the
    # alias still compile-fails cold ("mark it 'noncomputable'") with no
    # cold backstop. `noncomputable` is a property of the PROOF TERM, so
    # the strategy decl (`scratch_text`, when given) is the authority:
    # union it in. Visibility modifiers stay the stub's choice — the
    # public decl's author owns those.
    mods = leading_decl_modifiers(original, slug)
    if scratch_text and "noncomputable" not in mods:
        if "noncomputable" in leading_decl_modifiers(scratch_text, sid_token):
            mods = "noncomputable " + mods
    new_content = (
        annotation
        + "\n".join(orig_imports) + "\n\n"
        + f"namespace {namespace}\n\n"
        + f"{leading_decl_attrs(original, slug)}"
        # Carry the parent's keyword modifiers (`noncomputable` …) too, not
        # just its `@[...]` attrs. A data goal's stub is `noncomputable def
        # <slug> : <DataType> := by sorry`; without re-prepending the modifier
        # the re-export `def <slug> := @<sid>` compile-fails on cold `lake
        # build` with "mark it 'noncomputable'" (the sid IS noncomputable).
        # verify-collapse promotes this mechanically (no cold build) and a
        # trivial `main : True` root never imports the closure, so the broken
        # alias stays latent until harvest / review / a downstream import cold-
        # builds it. Attr-order: `@[attr]` precede `noncomputable` in Lean 4.
        + mods
        + f"def {slug} := @{namespace}.{sid_token}\n\n"
        + f"end {namespace}\n"
    )
    backup: Path | None = None
    if parent_abs.exists():
        backup = verify_backup_path(parent_abs, sid_token)
        shutil.copy2(parent_abs, backup)
    tmp = parent_abs.with_suffix(parent_abs.suffix + f".tmp_{sid_token}")
    tmp.write_text(new_content, encoding="utf-8")
    os.replace(tmp, parent_abs)
    return backup


def rollback_promote(parent_abs: Path, backup: Path | None) -> None:
    """Restore parent_abs from backup; delete backup. No-op if backup is None."""
    if backup is not None and backup.exists():
        shutil.copy2(backup, parent_abs)
        backup.unlink()
