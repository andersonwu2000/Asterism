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
# the strategy patch as the parent stub.
_DECL_HEAD_RE = r"\b(theorem|def|structure|class)\s+"


def signature_prefix(text: str, name: str) -> str:
    """Return the substring `<kind> <name> <binders> : <type>` (up to
    but not including `:=`). `<kind>` ∈ {theorem, def, structure,
    class}. Returns "" if no matching declaration head found.

    Walks balanced paren/brace/bracket depth so a top-level `:=` is
    distinguished from `:=` inside a binder default value or anonymous
    constructor literal.
    """
    m = re.search(_DECL_HEAD_RE + re.escape(name) + r"\b", text)
    if not m:
        return ""
    pos = m.end()
    n = len(text)
    depth = 0
    while pos < n - 1:
        ch = text[pos]
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth = max(0, depth - 1)
        elif depth == 0 and ch == ":" and text[pos + 1] == "=":
            return text[m.start():pos]
        pos += 1
    return text[m.start():]


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


def normalize_signature(s: str) -> str:
    """Collapse all whitespace runs to single spaces. Lets agents reformat
    indentation freely without tripping the diff check; only meaningful
    edits (binder names, types, theorem name) remain detectable."""
    return re.sub(r"\s+", " ", s).strip()


def build_strategy_skeleton(
    parent_text: str, *, parent_slug: str, sid_token: str,
    namespace: str,
) -> str | None:
    """Construct a strategy patch skeleton by copying the parent stub's
    `<kind> <parent_slug> ...` declaration verbatim, then renaming the
    declaration to `<sid_token>` and stubbing the body as `by sorry`.

    `<kind>` ∈ {theorem, def, structure, class} — the parent's keyword
    is preserved so the elaborator sees a matching declaration head
    (a `def`-parent's strategy patch stays a `def`, not a `theorem`).

    Returns None if no matching declaration head is found, or if the
    matched head has no top-level type colon. The latter case catches
    promoted-alias parents (`def g := @ns.sN`, no `:` between name
    and `:=`) and bare-value defs (`def g := 42`): Backward's
    signature lock requires a typed signature to be meaningful, so
    skip these cleanly rather than producing a typeless `def s := by
    sorry` skeleton that would fail at lake build with an unhelpful
    elaboration error.
    """
    sig = signature_prefix(parent_text, parent_slug)
    if not sig or not _has_top_level_type_colon(sig, parent_slug):
        return None
    new_sig = re.sub(
        _DECL_HEAD_RE + re.escape(parent_slug) + r"\b",
        lambda m: f"{m.group(1)} {sid_token}", sig, count=1,
    )
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
    header = "\n".join(imports)
    if opens:
        header += "\n" + "\n".join(opens)
    return (
        header + "\n\n"
        f"namespace {namespace}\n\n"
        f"{new_sig} := by sorry\n\n"
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
    new_content = (
        annotation
        + "\n".join(orig_imports) + "\n\n"
        + f"namespace {namespace}\n\n"
        + f"{leading_decl_attrs(original, slug)}"
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
