"""§13 audit stage — final free-form mathlib review of one Library file."""
from __future__ import annotations

import re
from pathlib import Path

from . import _common as C
from ._common import _Decl


# ---------------------------------------------------------------------
# §13 audit — final free-form mathlib review (full official conventions)
# ---------------------------------------------------------------------
# The LAST per-file stage (after decide). The agent holds the complete official
# mathlib style/naming/documentation conventions and rewrites the WHOLE file as
# a final reviewer — structure, sections, docstrings, normal forms, variable
# granularity, residual lints — full freedom, with three mechanical fences:
#   1. imports unchanged (decide owns them),
#   2. `namespace` lines unchanged (namespace-mount = v2; consumers' `open`
#      lines would need module-level rewiring),
#   3. every declaration's elaborated TYPE unchanged — modulo renames the agent
#      DECLARES in a renames.json sidecar (declared renames ride the existing
#      deferred-rewire channel exactly like decide's).
# Undeclared name changes / type drift → retry with the diff → revert.
# ---------------------------------------------------------------------

_AUDIT_PROMPT = "audit.md"
_AUDIT_OUTPUT = "audited.lean"
_AUDIT_RENAMES = "renames.json"
# 3 (was 2): audit now does the full mathlib-ize in one pass (polish folded in),
# so it gets one more attempt to converge to a clean, zero-warning rewrite.
_AUDIT_MAX_RETRIES = 3


def _audit_context(workspace: Path, problem: str, rel: str,
                   decl_names: "list[str]", prev_error: str = "") -> str:
    """Per-file context for the audit agent: module, declarations, the verbatim
    file, and (on retry) the violation / residual warnings to fix."""
    try:
        body = (workspace / rel).read_text(encoding="utf-8")
    except OSError:
        body = ""
    lines = [
        f"# Final mathlib review — {problem} — `{rel}`", "",
        f"Module: `{C._mod_of_rel(rel)}`.",
        f"Declarations: {', '.join(decl_names) or '(none)'}", "",
        "## Current file", "", "```lean", body.rstrip(), "```", "",
    ]
    if prev_error:
        lines += ["## Fix these and re-emit", "", "```", prev_error[-1800:],
                  "```", ""]
    return "\n".join(lines) + "\n"


def _header_fences(text: str) -> "tuple[list[str], list[str]]":
    """(sorted import lines, namespace-line sequence) — the two header shapes
    audit must keep byte-identical (order-insensitive for imports)."""
    imports = sorted(l.strip() for l in text.splitlines()
                     if l.strip().startswith("import "))
    namespaces = [l.strip() for l in text.splitlines()
                  if re.match(r"namespace\b", l.strip())]
    return imports, namespaces


def _json_loads_or_none(text: str):
    import json
    try:
        return json.loads(C._strip_json_fence(text))
    except Exception:  # noqa: BLE001
        return None


def file_cleanup_audit(workspace: Path, problem: str, target_file: str,
                       decls_in_file: "list[_Decl]", *,
                       scope: "list[_Decl]", pool: "list[_Decl]",
                       max_retries: int = _AUDIT_MAX_RETRIES
                       ) -> "tuple[dict[str, str], bool]":
    """§13 final-review audit for ONE file: free whole-file rewrite under the
    full official conventions, with declared-rename sidecar. Gate = imports +
    namespace fences, build, and #check type-invariance MODULO the declared
    renames (base type strings are token-rewritten old→new before comparing, so
    a sibling's type that mentions a renamed def still matches). Warning retry
    keeps the best green version (fewest warnings). Returns
    `({old_fqn: new_fqn} declared renames actually applied, file_changed)`."""
    prompt_path = workspace / "Tooling" / "prompts" / "librarian" / _AUDIT_PROMPT
    if not prompt_path.exists() or not decls_in_file:
        return {}, False
    leaf = target_file.split("/")[-1]
    module = C._mod_of_rel(target_file)
    try:
        original = (workspace / target_file).read_text(encoding="utf-8")
    except OSError:
        return {}, False
    # Nominal decls: snapshot the constructor too — `@Foo` alone is only the
    # signature, a field's type would otherwise drift unseen
    # (_common.nominal_ctor_suffixes).
    ctors = {d.name: C.nominal_ctor_suffixes(original, d.name)
             for d in decls_in_file}
    fqns = [d.fqn for d in decls_in_file] \
        + [f"{d.fqn}.{c}" for d in decls_in_file for c in ctors[d.name]]
    ok0, _d0, base_types = C._typecheck_capturing_types(workspace, original, fqns)
    if not ok0:
        print(f"[staged] audit `{leaf}` — skip (no type snapshot)", flush=True)
        return {}, False
    base_imports, base_namespaces = _header_fences(original)
    own_leaves = {d.name for d in decls_in_file}
    existing_leaves = {d.name for d in (*scope, *pool)} - own_leaves
    decl_names = [d.name for d in decls_in_file]
    prev_error = ""
    best: "tuple[int, str, dict[str, str]] | None" = None  # (warns, text, renames)
    for attempt in range(max_retries + 1):
        got = C.spawn_collect(
            workspace, problem, prompt_path,
            _audit_context(workspace, problem, target_file, decl_names,
                           prev_error),
            [_AUDIT_OUTPUT, _AUDIT_RENAMES])
        if got is None:
            prev_error = f"no {_AUDIT_OUTPUT} was produced"
            continue
        new_text = got[_AUDIT_OUTPUT]
        renames = C._valid_renames(
            C._coerce_renames(_json_loads_or_none(got[_AUDIT_RENAMES])
                              if _AUDIT_RENAMES in got else None),
            own_leaves=own_leaves, existing_leaves=existing_leaves)
        if new_text.strip() == original.strip() and not renames:
            return {}, False                      # already PR-ready — clean no-op
        new_imports, new_namespaces = _header_fences(new_text)
        if new_imports != base_imports or new_namespaces != base_namespaces:
            prev_error = ("the import block and the `namespace` lines must stay "
                          "EXACTLY as in the original (imports are the decide "
                          "stage's job; namespace-mount is out of scope) — "
                          "re-emit with them restored")
            continue
        # expected post-rename identity + type of every decl (+ nominal ctors:
        # a renamed class carries its ctor along, `Mod.New.mk`)
        leaf_map = {d.name: renames.get(d.name, d.name) for d in decls_in_file}
        pairs = [(d.name, d.fqn, f"{module}.{leaf_map[d.name]}")
                 for d in decls_in_file]
        pairs += [(f"{d.name}.{c}", f"{d.fqn}.{c}",
                   f"{module}.{leaf_map[d.name]}.{c}")
                  for d in decls_in_file for c in ctors[d.name]]
        fqns_after = [after for _, _, after in pairs]
        ok, detail, new_types = C._typecheck_capturing_types(
            workspace, new_text, fqns_after)
        if not ok:
            prev_error = detail
            continue
        changed = []
        for label, fqn_base, fqn_after in pairs:
            expected = base_types.get(fqn_base, "")
            for old, new in renames.items():     # sibling types may cite renamed
                expected, _ = C.replace_token(expected, old, new)
            if expected != new_types.get(fqn_after):
                changed.append(label)
        if changed:
            prev_error = ("the elaborated type changed for: "
                          + ", ".join(changed)
                          + " — restructure freely, but never what a "
                            "declaration PROVES (and declare any rename in "
                            f"{_AUDIT_RENAMES})")
            continue
        applied = {f"{module}.{o}": f"{module}.{n}" for o, n in renames.items()}
        # ALL warnings (not just polish's type-preserving subset): audit is the
        # final mathlib reviewer and must drive the file to ZERO — deprecated
        # lemmas, dupNamespace, etc. The per-file cleanup gate hard-fails on any
        # residual, so a non-zero "best" here just costs a unit retry.
        warns = C._all_warnings(
            C._build_for_warnings(workspace, new_text, prefix="_audit_warn")[1])
        if best is None or len(warns) < best[0]:
            best = (len(warns), new_text, applied)
        if not warns:
            break                                 # clean — done
        prev_error = ("the rewrite is green and type-safe, but these warnings "
                      "remain — clear them (Mathlib PR bar is ZERO; replace "
                      "deprecated lemmas with the suggested form, or as a last "
                      "resort `set_option <linter> false in` a single decl with "
                      "a one-line justification):\n" + "\n".join(warns[:10]))
    if best is None:
        print(f"[staged] audit `{leaf}` — kept original "
              f"(no green audit in {max_retries + 1} tries)", flush=True)
        return {}, False
    n_warn, text, applied = best
    (workspace / target_file).write_text(text, encoding="utf-8")
    print(f"[staged] audit `{leaf}` — applied ({n_warn} residual warning(s), "
          f"{len(applied)} renamed"
          + (": " + ", ".join(f"{o.rsplit('.', 1)[-1]}→{n.rsplit('.', 1)[-1]}"
                              for o, n in applied.items()) if applied else "")
          + ")", flush=True)
    return applied, True
