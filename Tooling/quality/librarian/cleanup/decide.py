"""§13 (P4) decide stage — naming alignment + precise imports."""
from __future__ import annotations

import re
from pathlib import Path

from . import _common as C
from ._common import _Decl


# ---------------------------------------------------------------------
# §13 (P4) decide — naming alignment + precise imports (supersedes rename)
# ---------------------------------------------------------------------
# The LAST per-file stage (after polish), on the final shape. Propose =
# pipeline-managed librarian spawn (kind="librarian" + decide.md) emitting
# decide.json {"renames": {old_leaf: new_leaf}, "imports": ["Mathlib.X.Y", …]};
# apply = MECHANICAL: whole-token rename of this file's decl header + in-file
# references, AND swap of the `import Mathlib` umbrella line for the proposed
# precise (canonical) module list. Per-file rebuild-gated with a degrade
# ladder — import-min is the risky half (LLM module choice), renames the
# proven half, so a red build falls back to renames-only (umbrella kept)
# before reverting everything. Library sibling imports are never touched.
# Cross-file consumers self-apply renames via the SAME deferred-rewire as
# drops (the caller records {old_fqn → new_fqn} to the DB rename channel).
# decide is the only stage that changes a file's EXPORTED names or its
# imports, so the caller refreshes the file's olean whenever it changed.
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
    """§13 (P4) decide pass for ONE file: propose mathlib-aligned names for this
    file's kept survivors AND a precise replacement for the `import Mathlib`
    umbrella (one pipeline-managed librarian spawn) → validate both → apply
    MECHANICALLY (whole-token rename of the decl header + every in-file
    reference; umbrella-line swap) → per-file rebuild gate. Degrade ladder on a
    red build: retry with error feedback → renames-only (umbrella kept) →
    revert. Writes ONLY `target_file`. Returns `({old_fqn: new_fqn} applied,
    imports_changed)` — empty/False = nothing to decide / prompt absent / no
    green candidate. Consumer files self-apply renames via deferred-rewire — the
    caller records them to the DB rename channel and refreshes this file's olean
    whenever it changed."""
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
    prev_error = ""
    # rung-3 candidate: renames-only text of the last red renames+imports try
    fallback: "tuple[str, dict[str, str]] | None" = None
    for attempt in range(max_retries + 1):
        got = C.spawn_collect(
            workspace, problem, prompt_path,
            _decide_context(workspace, problem, target_file, decls_in_file,
                            prev_error),
            [_DECIDE_OUTPUT])
        if got is None:
            prev_error = f"no {_DECIDE_OUTPUT} was produced"
            continue
        proposed_renames, proposed_imports = _parse_decide(got[_DECIDE_OUTPUT])
        renames = C._valid_renames(proposed_renames, own_leaves=own_leaves,
                                   existing_leaves=existing_leaves)
        imports = _valid_imports(proposed_imports, workspace)
        if not renames and not imports:
            print(f"[staged] decide `{leaf}` — nothing to decide", flush=True)
            return {}, False
        renamed_text = original
        applied: dict[str, str] = {}
        for old, new in renames.items():
            t, n = C.replace_token(renamed_text, old, new)
            if n:
                renamed_text = t
                applied[f"{module}.{old}"] = f"{module}.{new}"
        new_text, imports_changed = _swap_umbrella_import(renamed_text, imports)
        if new_text == original:
            return {}, False
        ok, detail = C._build_file_copy_isolated(workspace, new_text,
                                                 session_token=session_token)
        if not ok:
            if applied and imports_changed:
                fallback = (renamed_text, applied)
            prev_error = detail
            continue
        (workspace / target_file).write_text(new_text, encoding="utf-8")
        print(f"[staged] decide `{leaf}` — {len(applied)} renamed, "
              f"{len(imports) if imports_changed else 0} precise imports "
              f"(try {attempt + 1})"
              + (": " + ", ".join(
                  f"{o.rsplit('.', 1)[-1]}→{n.rsplit('.', 1)[-1]}"
                  for o, n in applied.items()) if applied else ""), flush=True)
        return applied, imports_changed
    # Degrade rung: every full candidate was red. The import swap is the risky
    # half (LLM module choice can be insufficient — missing instance/notation
    # deps); the renames were the proven half. Gate the last renames-only text
    # (umbrella kept) before giving up, so a bad import set never costs a rename.
    if fallback is not None:
        renamed_text, applied = fallback
        ok, _detail = C._build_file_copy_isolated(workspace, renamed_text,
                                                  session_token=session_token)
        if ok:
            (workspace / target_file).write_text(renamed_text, encoding="utf-8")
            print(f"[staged] decide `{leaf}` — {len(applied)} renamed; kept "
                  "`import Mathlib` (precise import set failed to build)",
                  flush=True)
            return applied, False
    print(f"[staged] decide `{leaf}` — kept original "
          f"(no green candidate in {max_retries + 1} tries)", flush=True)
    return {}, False
