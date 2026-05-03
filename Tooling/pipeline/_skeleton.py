"""F52 skeleton-driven strategy patch helpers + def-alias promotion.

Extracted from `pipeline/__init__.py` (P2-#1). Pure module: shared
helpers for Backward (skeleton + import injection) and Verify
(promote + rollback).
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from ._lake import lean_path_to_module


def signature_prefix(text: str, name: str) -> str:
    """Return the substring `theorem <name> <binders> : <type>` (up to but
    not including `:=`). Returns "" if `theorem <name>` not found.

    Walks balanced paren/brace/bracket depth so a top-level `:=` is
    distinguished from `:=` inside a binder default value or anonymous
    constructor literal.
    """
    m = re.search(rf"\btheorem\s+{re.escape(name)}\b", text)
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
    `theorem <parent_slug> ...` declaration verbatim, then renaming the
    theorem to `<sid_token>` and stubbing the body as `by sorry`.

    Returns None if `theorem <parent_slug>` is not found (e.g. parent
    was already promoted by a sibling and now contains `def ... := @...`
    instead — race-safe handling: caller aborts cleanly).
    """
    sig = signature_prefix(parent_text, parent_slug)
    if not sig:
        return None
    new_sig = re.sub(
        rf"\btheorem\s+{re.escape(parent_slug)}\b",
        f"theorem {sid_token}", sig, count=1,
    )
    imports = [ln for ln in parent_text.splitlines()
               if ln.strip().startswith("import")]
    if not imports:
        imports = ["import Mathlib"]
    return (
        "\n".join(imports) + "\n\n"
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
    """Backup filename keyed by sid_token (P0-#1) so concurrent
    Verifies on sibling strategies of the same parent goal can't
    clobber each other's backup."""
    return parent_abs.with_suffix(
        parent_abs.suffix + f".verify_backup_{sid_token}")


def promote_to_alias(
    parent_abs: Path, *,
    namespace: str, slug: str, sid_token: str,
    scratch_module: str,
) -> Path | None:
    """F52 — rewrite parent stub as a re-export alias of the strategy:
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
        "\n".join(orig_imports) + "\n\n"
        f"namespace {namespace}\n\n"
        f"def {slug} := @{namespace}.{sid_token}\n\n"
        f"end {namespace}\n"
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
