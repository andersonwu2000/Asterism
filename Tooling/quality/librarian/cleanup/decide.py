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
# Per-file rebuild-gated via a candidate LADDER (`_import_candidates`): the
# precise minImports set, then REMOVE (umbrella flagged unneeded), then the
# broader minImports∪dir-pool — first that builds wins. The detection build runs
# with a generous budget (`_IMPORT_BUMPS_TIMEOUT_SEC`: `#import_bumps` is cold +
# async-off, so 240s silently timed out → umbrella). Only when EVERY candidate
# fails the gate does the file degrade to renames-only (umbrella kept — never
# costs a rename); `library-verify` flags any surviving umbrella so it is never
# silent.
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
# `#import_bumps` forces `Elab.async false` (the minImports linter needs linear
# elaboration), making this cold build ~2-4× slower than a normal async one —
# and it can NEVER reuse a warm slot (its umbrella→minimal closure differs from
# the file slot, #108), so it is always a fresh `lake env lean`. The 240s
# `_BATCH_TIMEOUT_SEC` (calibrated for warm/async gates) silently timed out on
# the heavier residue files under pool load → no `-- missing imports` marker →
# the file degraded to the `import Mathlib` umbrella. This was the DOMINANT cause
# of the residue 7-file umbrella debt (2026-06-22): each file's own minimal set
# was correct, it just never finished computing in 240s. Give the detection build
# (and the cold rebuild-gate of an import-swapped candidate) their own generous
# budgets so the result is computed, not abandoned. 1200s ≈ 2× the heaviest
# residue file's isolated cold async-off build, headroom for concurrent pool load.
_IMPORT_BUMPS_TIMEOUT_SEC = 1200
_DECIDE_REBUILD_TIMEOUT_SEC = 480


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


def _remove_umbrella_import(text: str) -> "tuple[str, bool]":
    """Delete the `import Mathlib` umbrella line outright — for a file whose
    Mathlib dependencies are all covered TRANSITIVELY by its `import Library.*`
    siblings, so `#import_bumps` flags the umbrella as unneeded with no
    `Mathlib.X` replacement. `Library.*` sibling imports are untouched. Scans
    only the leading import/blank header block."""
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s == "import Mathlib":
            del lines[i]
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
# handles in-file references). Two of its outputs drive the umbrella decision:
#   • a consolidated `-- missing imports` block of plain `import Mathlib.X`
#     lines → the precise set to REPLACE the umbrella.
#   • `unneeded import 'Mathlib'` (with NO Mathlib.X in the missing block) →
#     the file's Mathlib deps come transitively through its `import Library.*`
#     siblings, so the umbrella should be REMOVED outright, not replaced.
# Both then rebuild-verify. Letting an LLM GUESS the set and retrying when it
# guessed wrong was a stochastic tool for a deterministic job: it left ~1/4 of
# files on the umbrella (a non-idiomatic artifact that mathlib forbids) and —
# worse, had we hard-gated it — would have reintroduced the cleanup STALL class
# (an unbuildable guessed set with no fallback).
# (`lake exe shake`, the old CI minimiser, is dead under the module system.)

_IMPORT_BUMPS_MARKER = "-- missing imports"
_MIN_IMPORT_LINE_RE = re.compile(r"^\s*import\s+(Mathlib\.[A-Za-z0-9_.']+)\s*$")
# `warning: unneeded import 'Mathlib'` — the bare umbrella (the quoted
# `'Mathlib'` cannot match `'Mathlib.X'`, so this never fires on a precise one).
_UNNEEDED_UMBRELLA_RE = re.compile(r"unneeded import 'Mathlib'")


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


def _compute_min_imports(workspace: Path,
                         content: str) -> "tuple[list[str], bool]":
    """Mechanically compute the umbrella replacement for `content` (which still
    carries `import Mathlib`) via mathlib's `#import_bumps`. Returns
    `(mathlib_imports, umbrella_unneeded)`:
      - `mathlib_imports`: existence-checked, sorted `Mathlib.*` set to REPLACE
        the umbrella (`[]` when the linter surfaced no missing block).
      - `umbrella_unneeded`: True when `#import_bumps` flags `import Mathlib`
        itself as unneeded — its deps are covered transitively (via `Library.*`
        siblings), so with no `Mathlib.*` replacement the umbrella is REMOVED.
    COLD build: the consolidated block is raw `lean` output the warm `/verify`
    path may reshape. Both outcomes are candidates only; the caller
    rebuild-verifies (the linter has a documented attribute gap), so an
    incomplete result degrades to umbrella-kept rather than a broken file."""
    _ok, out = C._build_with_output(
        workspace, _inject_import_bumps(content), prefix="importmin",
        timeout=_IMPORT_BUMPS_TIMEOUT_SEC, session_token=None)
    imports = _valid_imports(_parse_missing_imports(out), workspace)
    return imports, bool(_UNNEEDED_UMBRELLA_RE.search(out))


def _dir_precise_imports(workspace: Path, target_file: str) -> "list[str]":
    """Union of the precise `import Mathlib.*` lines across the SIBLING files in
    `target_file`'s Library subdirectory (existence-checked, sorted). The
    empirical 'common instance modules' pool: when a file's OWN minimal set (or
    the REMOVE verdict) fails the rebuild gate — the minImports linter
    under-reports an instance/elaboration module it can't see as a constant
    reference — these are the modules the file's neighbours actually needed, a
    broader candidate that may cover the gap. Files still on the `import Mathlib`
    umbrella contribute nothing (no `Mathlib.X` lines), so the pool grows richer
    as the dependency-ordered cleanup proceeds. Used ONLY as a UNION with the
    file's own minimal set (never alone): the own set always carries that file's
    unique deps, which a cross-file pool can lack."""
    rel = target_file.replace("\\", "/")
    self_path = workspace / rel
    pool: set[str] = set()
    for p in sorted(self_path.parent.glob("*.lean")):
        if p == self_path:
            continue
        try:
            txt = p.read_text(encoding="utf-8")
        except OSError:
            continue
        for ln in txt.splitlines():
            m = _MIN_IMPORT_LINE_RE.match(ln)
            if m:
                pool.add(m.group(1))
            elif ln.strip() and not ln.lstrip().startswith("import "):
                break                       # past the import header
    return _valid_imports(sorted(pool), workspace)


def _import_candidates(workspace: Path, target_file: str, renamed_text: str,
                       imports: "list[str]", umbrella_unneeded: bool
                       ) -> "list[tuple[str, str]]":
    """Ordered umbrella-replacement candidates for the rebuild ladder, cleanest
    first; the caller rebuild-gates them in order and takes the FIRST that builds.
    Each entry is `(new_text, human_desc)`. Order:
      1. SWAP(minImports set)        — the precise, idiomatic target.
      2. REMOVE                      — when the set is empty but the linter
                                       flagged the umbrella itself unneeded.
      3. SWAP(minImports ∪ dir-pool) — broader fallback covering an
                                       instance/elaboration module the linter
                                       under-reported (see `_dir_precise_imports`).
    A no-op or a duplicate of an earlier candidate is dropped, so when the pool
    adds nothing (1 == 3) the ladder collapses to the single precise candidate."""
    out: "list[tuple[str, str]]" = []
    seen: set[str] = set()

    def add(text: str, changed: bool, desc: str) -> None:
        if changed and text not in seen:
            seen.add(text)
            out.append((text, desc))

    if imports:
        t, ch = _swap_umbrella_import(renamed_text, imports)
        add(t, ch, f"{len(imports)} precise imports")
    elif umbrella_unneeded:
        t, ch = _remove_umbrella_import(renamed_text)
        add(t, ch, "dropped umbrella (siblings cover)")
    broad = sorted(set(imports) | set(_dir_precise_imports(workspace, target_file)))
    if broad:
        t, ch = _swap_umbrella_import(renamed_text, broad)
        add(t, ch, f"{len(broad)} imports (dir-pool fallback)")
    return out


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
    # An ordered candidate ladder (`_import_candidates`, cleanest first): the
    # precise minImports set, else REMOVE when the umbrella is flagged unneeded,
    # else the broader minImports∪dir-pool. Each is rebuild-gated COLD (an
    # import-swapped candidate's closure differs from the warm umbrella slot, so
    # the warm path would re-warm and evict it, #108) with a generous budget; the
    # FIRST that builds wins. The linter under-reports instance/elaboration
    # modules, so the precise primary can fail the gate — the ladder broadens
    # before resorting to the umbrella (which a mathlib PR forbids).
    imports, umbrella_unneeded = _compute_min_imports(workspace, renamed_text)
    candidates = _import_candidates(workspace, target_file, renamed_text,
                                    imports, umbrella_unneeded)
    built_text, imp_desc = None, ""
    for cand_text, desc in candidates:
        ok, _detail = C._build_file_copy_isolated(
            workspace, cand_text, timeout=_DECIDE_REBUILD_TIMEOUT_SEC,
            session_token=None)
        if ok:
            built_text, imp_desc = cand_text, desc
            break
    if built_text is not None:                  # an import candidate built
        (workspace / target_file).write_text(built_text, encoding="utf-8")
        print(f"[staged] decide `{leaf}` — {len(applied)} renamed, "
              f"{imp_desc} (mechanical)"
              + (": " + ", ".join(
                  f"{o.rsplit('.', 1)[-1]}→{n.rsplit('.', 1)[-1]}"
                  for o, n in applied.items()) if applied else ""), flush=True)
        return applied, True
    # --- 3. degrade: every import candidate broke the build (the minImports set
    # hit the linter's attribute gap and even the dir-pool couldn't cover it).
    # Keep the umbrella so a bad set never costs a rename; the umbrella is rare
    # now and `library-verify` flags any that survive, so it is never silent.
    # Preserve renames if they build on the (kept-umbrella) shape — a renames-only
    # red build is the renames' own fault, so revert those.
    if renamed_text == original:
        note = ("kept `import Mathlib` (mechanical import set failed to build)"
                if candidates else "nothing to decide")
        print(f"[staged] decide `{leaf}` — {note}", flush=True)
        return {}, False
    ok2, _ = C._build_file_copy_isolated(
        workspace, renamed_text, timeout=_DECIDE_REBUILD_TIMEOUT_SEC,
        session_token=session_token)
    if applied and ok2:
        (workspace / target_file).write_text(renamed_text, encoding="utf-8")
        print(f"[staged] decide `{leaf}` — {len(applied)} renamed; kept "
              "`import Mathlib` (mechanical import set failed to build)",
              flush=True)
        return applied, False
    print(f"[staged] decide `{leaf}` — kept `import Mathlib` "
          "(mechanical import set failed to build)", flush=True)
    return {}, False
