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
#
# The agent edits `audited.lean` (seeded with the original) through the LSP
# gateway: `mcp__lsp__apply_edit` for targeted edits, `mcp__lsp__errors_at` to
# read the live diagnostics and drive every warning to zero — the same edit-mode
# the builder / migrate-hole-fill pipelines use. The retry loop is the shared
# `run_with_session_retries` (cold-seed → warm incremental, --resume session
# memory), NOT a from-scratch whole-file rewrite each attempt.
# ---------------------------------------------------------------------

_AUDIT_PROMPT = "audit.md"
_AUDIT_OUTPUT = "audited.lean"
_AUDIT_RENAMES = "renames.json"
# 3 (was 2): audit now does the full mathlib-ize in one pass (polish folded in),
# so it gets one more attempt to converge to a clean, zero-warning rewrite.
_AUDIT_MAX_RETRIES = 3

_FENCE_MSG = ("the import block and the `namespace` lines must stay EXACTLY as "
              "in the original (imports are the decide stage's job; "
              "namespace-mount is out of scope) — restore them")
_TYPE_MSG = ("the elaborated type changed for: {decls} — restructure freely, "
             "but never what a declaration PROVES. An unused *hypothesis* binder "
             "must be `_`-prefixed (e.g. `hX` → `_hX`) to silence its lint, NOT "
             "deleted: the binder stays in the signature (a sibling may still "
             "pass it, and the type gate rejects an arity change). Declare any "
             "rename in " + _AUDIT_RENAMES)
_WARN_MSG = ("the rewrite is green and type-safe, but these warnings remain — "
             "clear them (Mathlib PR bar is ZERO; replace deprecated lemmas with "
             "the suggested form, `_`-prefix an unused hypothesis binder instead "
             "of deleting it, or as a last resort `set_option <linter> false in` "
             "a single decl with a one-line justification):\n")


def _audit_context(workspace: Path, problem: str, rel: str,
                   decl_names: "list[str]") -> str:
    """Per-file context (cold spawn) for the audit agent: module, declarations,
    and the verbatim file. Retry feedback (gate violation / residual warnings)
    flows through `run_with_session_retries`' `retry_context`, not here."""
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
    return "\n".join(lines) + "\n"


def _header_fences(text: str) -> "tuple[list[str], list[str]]":
    """(sorted import lines, namespace-line sequence) — the two header shapes
    audit must keep byte-identical (order-insensitive for imports)."""
    imports = sorted(l.strip() for l in text.splitlines()
                     if l.strip().startswith("import "))
    namespaces = [l.strip() for l in text.splitlines()
                  if re.match(r"namespace\b", l.strip())]
    return imports, namespaces


def _json_loads_or_none(text: "str | None"):
    import json
    if text is None:
        return None
    try:
        return json.loads(C._strip_json_fence(text))
    except Exception:  # noqa: BLE001
        return None


# --- gate (pure): validate one audited candidate against the three fences -----
# Separated from the spawn/retry shell so the fence + type-invariance + warning
# logic is independently unit-testable (the shell needs a live LSP gateway).
# The type gate is STRICTLY invariant (modulo declared renames): an unused
# hypothesis binder is handled by `_`-prefixing it (type-preserving — an unused
# hypothesis is non-dependent, so `#check @decl` prints it in arrow form with no
# binder name → the rename is invisible here), NOT by dropping it (an arity
# change that a cross-file consumer's call site would silently break).

def _audit_gate(workspace: Path, target_file: str,
                decls_in_file: "list[_Decl]", *, original: str, new_text: str,
                renames_raw: "str | None", base_types: "dict[str, str]",
                scope: "list[_Decl]", pool: "list[_Decl]"
                ) -> "tuple[str, str, dict[str, str], list[str]]":
    """Validate the agent's `audited.lean` candidate. Returns
    `(status, detail, applied_renames, warns)` where status is one of:
      - `noop`  — identical to the original (already PR-ready), no renames
      - `fence` — import / namespace fence violated
      - `build` — the rewrite does not typecheck
      - `type`  — a declaration's elaborated type drifted (beyond declared rename)
      - `ok`    — green, type-safe, ZERO warnings
      - `warn`  — green, type-safe, but residual warnings remain
    `applied_renames` ({old_fqn: new_fqn}) and `warns` are populated for
    `ok`/`warn` only. `base_types` is the one-shot snapshot of every decl's
    (and nominal ctor's) elaborated type, keyed by BEFORE-fqn."""
    module = C._mod_of_rel(target_file)
    own_leaves = {d.name for d in decls_in_file}
    existing_leaves = {d.name for d in (*scope, *pool)} - own_leaves
    base_imports, base_namespaces = _header_fences(original)
    # Nominal decls: snapshot the constructor too — `@Foo` alone is only the
    # signature; a field's type would otherwise drift unseen.
    ctors = {d.name: C.nominal_ctor_suffixes(original, d.name)
             for d in decls_in_file}
    renames = C._valid_renames(
        C._coerce_renames(_json_loads_or_none(renames_raw)),
        own_leaves=own_leaves, existing_leaves=existing_leaves)
    if new_text.strip() == original.strip() and not renames:
        return "noop", "", {}, []
    new_imports, new_namespaces = _header_fences(new_text)
    if new_imports != base_imports or new_namespaces != base_namespaces:
        return "fence", _FENCE_MSG, {}, []
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
        return "build", detail, {}, []
    changed = []
    for label, fqn_base, fqn_after in pairs:
        expected = base_types.get(fqn_base, "")
        for old, new in renames.items():        # sibling types may cite renamed
            expected, _ = C.replace_token(expected, old, new)
        if expected != (new_types.get(fqn_after) or ""):
            changed.append(label)
    if changed:
        return "type", _TYPE_MSG.format(decls=", ".join(changed)), {}, []
    applied = {f"{module}.{o}": f"{module}.{n}" for o, n in renames.items()}
    # ALL warnings (not just polish's type-preserving subset): audit is the
    # final mathlib reviewer and must drive the file to ZERO — deprecated
    # lemmas, dupNamespace, unused variable, etc. The per-file cleanup gate
    # hard-fails on any residual, so a non-zero best here just costs a retry.
    warns = C._all_warnings(
        C._build_for_warnings(workspace, new_text, prefix="_audit_warn")[1])
    return ("ok" if not warns else "warn"), "", applied, warns


def file_cleanup_audit(workspace: Path, problem: str, target_file: str,
                       decls_in_file: "list[_Decl]", *,
                       scope: "list[_Decl]", pool: "list[_Decl]",
                       conn=None, pipeline_id: "str | None" = None,
                       max_retries: int = _AUDIT_MAX_RETRIES
                       ) -> "tuple[dict[str, str], bool]":
    """§13 final-review audit for ONE file: a free whole-file mathlib rewrite
    under the full official conventions, driven through the shared LSP edit-mode
    retry loop (`run_with_session_retries`, like builder / migrate-hole-fill).
    The agent edits `audited.lean` (cold-seeded with the original) via the LSP
    gateway; each rc==0 spawn is gated on imports + namespace fences, build, and
    #check type-invariance MODULO declared renames, then driven to ZERO
    warnings. Warm retries keep the prior `audited.lean` (incremental) and
    resume the same session; the loop keeps the greenest version (fewest
    warnings). Returns `({old_fqn: new_fqn} declared renames actually applied,
    file_changed)`.

    `conn` / `pipeline_id` thread the cleanup pipeline's DB connection + id for
    forensic linkage; both are optional (the retry loop runs with `goal_id=None`,
    so `conn` is unused — audit is a per-FILE unit, not a goal-bound pipeline)."""
    from .... import agent
    from ....core import dispatcher
    from ....pipeline import PipelineResult, _feedback
    from ....pipeline._retry import SpawnCtx, run_lsp_edit_loop

    prompt_path = workspace / "Tooling" / "prompts" / "librarian" / _AUDIT_PROMPT
    if not prompt_path.exists() or not decls_in_file:
        return {}, False
    leaf = target_file.split("/")[-1]
    try:
        original = (workspace / target_file).read_text(encoding="utf-8")
    except OSError:
        return {}, False
    # One-shot type snapshot (+ nominal ctors) — the type-invariance gate
    # compares every candidate against this.
    ctors = {d.name: C.nominal_ctor_suffixes(original, d.name)
             for d in decls_in_file}
    fqns = [d.fqn for d in decls_in_file] \
        + [f"{d.fqn}.{c}" for d in decls_in_file for c in ctors[d.name]]
    ok0, _d0, base_types = C._typecheck_capturing_types(workspace, original, fqns)
    if not ok0:
        print(f"[staged] audit `{leaf}` — skip (no type snapshot)", flush=True)
        return {}, False

    problem_dir = workspace.joinpath("Problems", *problem.split("."))
    # Path-safe id (no `:` — it is also the attempts dir name; Windows forbids
    # `:` in a path component). Strip the `.lean` suffix for a clean dir name.
    stem = leaf[:-5] if leaf.endswith(".lean") else leaf
    pid = f"{pipeline_id or agent.new_pipeline_id()}-audit-{stem}"
    attempts = agent.attempts_dir_for(workspace, pid)
    audited = attempts / _AUDIT_OUTPUT
    renames_file = attempts / _AUDIT_RENAMES
    decl_names = [d.name for d in decls_in_file]

    best: "tuple[int, str, dict[str, str]] | None" = None  # (warns, text, renames)
    cap: "dict[str, bool]" = {}

    def cold_prep(ctx: SpawnCtx) -> None:
        # Seed audited.lean = the original + write Context.md; the agent EDITS
        # audited.lean in place via LSP (apply_edit write-through). Warm retries
        # keep the agent's last audited.lean (incremental, --resume) so
        # retry_context-driven warning fixes build on the prior pass, not a
        # from-scratch whole-file rewrite — so cold_prep runs on cold only.
        (ctx.attempts_dir / "Context.md").write_text(
            _audit_context(workspace, problem, target_file, decl_names),
            encoding="utf-8")
        audited.write_text(original, encoding="utf-8")
        if renames_file.exists():
            renames_file.unlink()

    def parse() -> PipelineResult:
        nonlocal best
        if not audited.exists():
            return PipelineResult(
                outcome="failed", failure_reason="agent_no_output",
                failure_detail=f"audit {leaf}: no {_AUDIT_OUTPUT}")
        new_text = audited.read_text(encoding="utf-8")
        renames_raw = (renames_file.read_text(encoding="utf-8")
                       if renames_file.exists() else None)
        status, detail, applied, warns = _audit_gate(
            workspace, target_file, decls_in_file, original=original,
            new_text=new_text, renames_raw=renames_raw, base_types=base_types,
            scope=scope, pool=pool)
        if status == "noop":
            cap["noop"] = True
            return PipelineResult(outcome="success")
        if status in ("fence", "build", "type"):
            # Non-terminal: feed the diff back as retry_context and re-spawn.
            return PipelineResult(
                outcome="failed", failure_reason="librarian_gate_failed",
                failure_detail=detail)
        # ok / warn — track the greenest (fewest-warning) version seen.
        if best is None or len(warns) < best[0]:
            best = (len(warns), new_text, applied)
        if status == "ok":
            return PipelineResult(outcome="success")
        return PipelineResult(
            outcome="failed", failure_reason="librarian_warnings_remain",
            failure_detail=_WARN_MSG + "\n".join(warns[:10]))

    def feedback(sid: str, result: "PipelineResult") -> None:
        _feedback.attempt_feedback(
            kind="cleanup:audit", sid=sid, slug=leaf,
            outcome=("success" if result.outcome == "success" else "exhausted"),
            problem_dir=problem_dir, attempts_dir=attempts, workspace=workspace)

    # `release_session_after=True`: free this audit's gateway slot before the
    # next file registers (the cleanup chain runs files back-to-back).
    run_lsp_edit_loop(
        conn=conn, goal_id=None, pipeline_id=pid,
        budget_threshold=max_retries + 1,
        shelve_threshold=dispatcher.SHELVE_THRESHOLD,
        attempts_dir=attempts, workspace=workspace,
        problem=problem, problem_dir=problem_dir,
        kind="librarian", prompt_path=prompt_path, target=audited,
        cold_prep_fn=cold_prep, parse_fn=parse,
        feedback_fn=feedback, release_session_after=True)

    if best is None:
        if not cap.get("noop"):
            print(f"[staged] audit `{leaf}` — kept original (no green audit in "
                  f"{max_retries + 1} tries)", flush=True)
        return {}, False                          # noop or no green candidate
    n_warn, text, applied = best
    (workspace / target_file).write_text(text, encoding="utf-8")
    print(f"[staged] audit `{leaf}` — applied ({n_warn} residual warning(s), "
          f"{len(applied)} renamed"
          + (": " + ", ".join(f"{o.rsplit('.', 1)[-1]}→{n.rsplit('.', 1)[-1]}"
                              for o, n in applied.items()) if applied else "")
          + ")", flush=True)
    return applied, True
