"""§13 (P4) decide stage — naming alignment (LLM) + precise imports (mechanical)."""
from __future__ import annotations

import re
from pathlib import Path

from . import _common as C
from ._common import _Decl


# ---------------------------------------------------------------------
# §13 (P4) decide — naming alignment (LLM) + precise imports (mechanical)
# ---------------------------------------------------------------------
# The LAST per-file stage (after polish), on the final shape. Two concerns:
#   • RENAMES — a judgment call (which names are idiomatic): pipeline-managed
#     librarian spawn (kind="librarian" + decide.md) emitting decide.json
#     {"renames": {old_leaf: new_leaf}}; apply = MECHANICAL whole-token rename
#     of this file's decl header + in-file references.
#   • IMPORTS — a deterministic fact (the modules the file actually uses), so
#     computed MECHANICALLY (`#import_bumps`, see `_compute_min_imports`), NOT
#     by the LLM. The umbrella `import Mathlib` is swapped for that set.
# Per-file rebuild-gated: the swapped+renamed file must build. The mechanical
# import set is complete by construction in the common case; on the rare linter
# gap the file degrades to renames-only (umbrella kept — never costs a rename),
# and `library-verify` flags any surviving umbrella so it is never silent.
# Library sibling imports are never touched. Cross-file consumers self-apply
# renames via the SAME deferred-rewire as drops (the caller records {old_fqn →
# new_fqn} to the DB rename channel). decide is the only stage that changes a
# file's EXPORTED names or its imports, so the caller refreshes its olean
# whenever it changed.
# ---------------------------------------------------------------------

_DECIDE_PROMPT = "decide.md"
_DECIDE_OUTPUT = "decide.json"
_DECIDE_MAX_RETRIES = 1
_MATHLIB_IMPORT_RE = re.compile(r"^Mathlib(\.[A-Za-z0-9_'][A-Za-z0-9_']*)+$")


def _parse_decide(text: str) -> "tuple[dict[str, str], list[str]]":
    """Parse the decide agent's output → (renames, imports). Canonical shape is
    `{"renames": {...}, "imports": [...]}`; a bare str→str object (the legacy
    renames.json shape) is tolerated as renames-only. Missing/empty `imports`
    = keep the `import Mathlib` umbrella (no-op)."""
    import json
    try:
        data = json.loads(C._strip_json_fence(text))
    except Exception:  # noqa: BLE001
        return {}, []
    if isinstance(data, dict) and ("renames" in data or "imports" in data):
        renames = C._coerce_renames(data.get("renames"))
        raw = data.get("imports")
        imports = [m.strip() for m in raw
                   if isinstance(m, str) and m.strip()] if isinstance(raw, list) else []
        return renames, imports
    return C._coerce_renames(data), []


def _valid_imports(proposed: "list[str]", workspace: Path) -> "list[str]":
    """Keep only real Mathlib module paths: shape `Mathlib.A.B` (≥ 1 segment —
    the bare `Mathlib` umbrella is not a proposal) AND the module file exists in
    the vendored mathlib. The existence check kills hallucinated paths for free,
    before the expensive build; the rebuild gate is the real sufficiency check.
    Returns the surviving set sorted (mathlib import-block convention), deduped."""
    root = workspace / ".lake" / "packages" / "mathlib"
    out: set[str] = set()
    for m in proposed:
        if not _MATHLIB_IMPORT_RE.match(m):
            continue
        if not (root / (m.replace(".", "/") + ".lean")).is_file():
            continue
        out.add(m)
    return sorted(out)


def _swap_umbrella_import(text: str, imports: "list[str]") -> "tuple[str, bool]":
    """Replace the `import Mathlib` umbrella line in the file header with the
    precise import list (one `import Mathlib.X` per line, caller-sorted).
    `Library.*` sibling imports are untouched. Scans only the leading
    import/blank header block; no umbrella there (or no imports) → no-op."""
    if not imports:
        return text, False
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s == "import Mathlib":
            lines[i:i + 1] = [f"import {m}" for m in imports]
            return "\n".join(lines), True
        if s and not s.startswith("import "):
            break                       # past the header — no umbrella line
    return text, False


# ---------------------------------------------------------------------
# Mechanical precise-import computation (replaces the LLM import proposal)
# ---------------------------------------------------------------------
# Imports are a deterministic fact — the set of modules defining the constants,
# instances, notation and tactics a file uses — not a judgment call. mathlib
# ships the exact tool: `#import_bumps` drives the `minImports` linter (which,
# unlike the `#min_imports in` command, accounts for notation + tactic info and
# handles in-file references), printing a consolidated `-- missing imports`
# block of plain `import Mathlib.X` lines. We compute that set, swap it for the
# `import Mathlib` umbrella, and rebuild-verify. Letting an LLM GUESS the set and
# retrying when it guessed wrong was a stochastic tool for a deterministic job:
# it left ~1/4 of files on the umbrella (a non-idiomatic artifact that mathlib
# forbids) and — worse, had we hard-gated it — would have reintroduced the
# cleanup STALL class (an unbuildable guessed set with no fallback).
# (`lake exe shake`, the old CI minimiser, is dead under the module system.)

_IMPORT_BUMPS_MARKER = "-- missing imports"
_MIN_IMPORT_LINE_RE = re.compile(r"^\s*import\s+(Mathlib\.[A-Za-z0-9_.']+)\s*$")


def _inject_import_bumps(text: str) -> str:
    """Insert mathlib's `#import_bumps` right after the import block so the
    `minImports` linter reports this file's minimal import set on the next
    build. `#import_bumps` itself sets `Elab.async false` + `linter.minImports
    true` (linear parsing — the linter needs it)."""
    lines = text.splitlines(keepends=True)
    k = max((i + 1 for i, ln in enumerate(lines)
             if ln.lstrip().startswith("import ")), default=0)
    return "".join(lines[:k]) + "#import_bumps\n" + "".join(lines[k:])


def _parse_missing_imports(build_output: str) -> "list[str]":
    """Parse the consolidated `-- missing imports` block `#import_bumps` prints
    → the minimal `Mathlib.*` module set (deduped, source order). Empty if the
    marker is absent (linter unavailable, or the file genuinely needs no precise
    Mathlib import). Only `Mathlib.*` lines are taken — a `Library.*` sibling in
    the block is already an explicit import and is never touched here."""
    lines = build_output.splitlines()
    idx = next((i for i, ln in enumerate(lines)
                if _IMPORT_BUMPS_MARKER in ln), None)
    if idx is None:
        return []
    out: list[str] = []
    for ln in lines[idx + 1:]:
        m = _MIN_IMPORT_LINE_RE.match(ln)
        if m:
            if m.group(1) not in out:
                out.append(m.group(1))
        elif ln.strip() and not ln.lstrip().startswith("import "):
            break                       # past the import block
    return out


def _compute_min_imports(workspace: Path, content: str) -> "list[str]":
    """Mechanically compute the minimal `Mathlib.*` imports for `content` (which
    still carries the `import Mathlib` umbrella) via mathlib's `#import_bumps`.
    Returns the existence-checked, sorted module list — `[]` to keep the umbrella
    (linter produced nothing / build did not surface the block). COLD build: the
    consolidated block is raw `lean` output the warm `/verify` path may reshape.
    The returned set is a candidate only; the caller rebuild-verifies it (the
    linter has a documented attribute gap), so an incomplete set is caught."""
    _ok, out = C._build_with_output(
        workspace, _inject_import_bumps(content), prefix="importmin",
        session_token=None)
    return _valid_imports(_parse_missing_imports(out), workspace)


def _decide_context(workspace: Path, problem: str, rel: str,
                    decls_in_file: "list[_Decl]", prev_error: str = "") -> str:
    """Per-file context for the decide agent: module, the renamable declarations
    with their statements, the verbatim file, and (on retry) the build error."""
    try:
        body = (workspace / rel).read_text(encoding="utf-8")
    except OSError:
        body = ""
    lines = [
        f"# Naming + imports — {problem} — `{rel}`", "",
        f"Module: `{C._mod_of_rel(rel)}`.",
        "Declarations you may rename (kept survivors in THIS file):", "",
    ]
    lines += [f"- `{d.name}` : `{' '.join(d.sig.split())}`"
              for d in decls_in_file] or ["- (none)"]
    lines += ["", "## Current file", "", "```lean", body.rstrip(), "```", ""]
    if prev_error:
        lines += ["## Your previous proposal failed to build — fix and retry",
                  "", "```", prev_error[-1500:], "```", ""]
    return "\n".join(lines) + "\n"


def file_cleanup_decide(workspace: Path, problem: str, target_file: str,
                        decls_in_file: "list[_Decl]", *,
                        scope: "list[_Decl]", pool: "list[_Decl]",
                        max_retries: int = _DECIDE_MAX_RETRIES,
                        session_token: "str | None" = None
                        ) -> "tuple[dict[str, str], bool]":
    """§13 (P4) decide pass for ONE file. (1) RENAMES — one librarian spawn
    proposes mathlib-aligned names for this file's kept survivors; applied
    MECHANICALLY (whole-token rename of the decl header + every in-file
    reference). (2) IMPORTS — the precise replacement for the `import Mathlib`
    umbrella is computed MECHANICALLY via `#import_bumps` (no LLM), then swapped
    in. The renamed + import-swapped file is rebuild-gated; on the rare linter
    gap it degrades to renames-only (umbrella kept — never costs a rename).
    Writes ONLY `target_file`. Returns `({old_fqn: new_fqn} applied,
    imports_changed)` — empty/False = nothing to decide / prompt absent.
    Consumer files self-apply renames via deferred-rewire — the caller records
    them to the DB rename channel and refreshes this file's olean whenever it
    changed."""
    prompt_path = workspace / "Tooling" / "prompts" / "librarian" / _DECIDE_PROMPT
    if not prompt_path.exists() or not decls_in_file:
        return {}, False
    leaf = target_file.split("/")[-1]
    module = C._mod_of_rel(target_file)
    # No cross-problem guard: by design a problem is cleaned BEFORE any other
    # problem may cite it (clean-before-cite), so at rename time this problem has
    # no external citer — the keystone `main` and every other decl rename freely,
    # and same-problem consumers self-apply via deferred-rewire. Gate B / INDEX
    # cite the keystone by DB target_name (which set_library_renamed updates), so
    # renaming `main` flows through. (A stray dev-phase cross-problem ref can only
    # arise from cleaning out of dependency order; cross-problem rewire, if ever
    # needed, is future work — as for drops.)
    own_leaves = {d.name for d in decls_in_file}
    existing_leaves = {d.name for d in (*scope, *pool)} - own_leaves
    try:
        original = (workspace / target_file).read_text(encoding="utf-8")
    except OSError:
        return {}, False
    # --- 1. renames (LLM judgment — the one part that needs taste) ----------
    renames: dict[str, str] = {}
    prev_error = ""
    for _attempt in range(max_retries + 1):
        got = C.spawn_collect(
            workspace, problem, prompt_path,
            _decide_context(workspace, problem, target_file, decls_in_file,
                            prev_error),
            [_DECIDE_OUTPUT])
        if got is None:
            prev_error = f"no {_DECIDE_OUTPUT} was produced"
            continue
        proposed_renames, _ = _parse_decide(got[_DECIDE_OUTPUT])
        renames = C._valid_renames(proposed_renames, own_leaves=own_leaves,
                                   existing_leaves=existing_leaves)
        break                                   # got an answer ({} is valid)
    renamed_text = original
    applied: dict[str, str] = {}
    for old, new in renames.items():
        t, n = C.replace_token(renamed_text, old, new)
        if n:
            renamed_text = t
            applied[f"{module}.{old}"] = f"{module}.{new}"
    # --- 2. imports (MECHANICAL — #import_bumps, no LLM guess/retry) --------
    imports = _compute_min_imports(workspace, renamed_text)
    new_text, imports_changed = _swap_umbrella_import(renamed_text, imports)
    if new_text == original:
        print(f"[staged] decide `{leaf}` — nothing to decide", flush=True)
        return {}, False
    ok, _detail = C._build_file_copy_isolated(workspace, new_text,
                                              session_token=session_token)
    if ok:
        (workspace / target_file).write_text(new_text, encoding="utf-8")
        print(f"[staged] decide `{leaf}` — {len(applied)} renamed, "
              f"{len(imports) if imports_changed else 0} precise imports "
              "(mechanical)"
              + (": " + ", ".join(
                  f"{o.rsplit('.', 1)[-1]}→{n.rsplit('.', 1)[-1]}"
                  for o, n in applied.items()) if applied else ""), flush=True)
        return applied, imports_changed
    # --- 3. degrade: the import swap broke the build (mechanical set hit the
    # linter's attribute gap / a module-system edge). Keep the umbrella so a bad
    # import set never costs a rename; the umbrella is rare now and
    # `library-verify` flags any that survive, so it is never silent. Only worth
    # a retry when the swap is what changed (imports_changed) AND there were
    # renames to preserve — a renames-only red build is the renames' own fault
    # and reverting is the right move.
    if applied and imports_changed:
        ok2, _ = C._build_file_copy_isolated(workspace, renamed_text,
                                             session_token=session_token)
        if ok2:
            (workspace / target_file).write_text(renamed_text, encoding="utf-8")
            print(f"[staged] decide `{leaf}` — {len(applied)} renamed; kept "
                  "`import Mathlib` (mechanical import set failed to build)",
                  flush=True)
            return applied, False
    print(f"[staged] decide `{leaf}` — kept `import Mathlib` "
          "(mechanical import set failed to build)", flush=True)
    return {}, False
