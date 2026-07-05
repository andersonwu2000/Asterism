"""§13 audit stage — final free-form mathlib review of one Library file."""
from __future__ import annotations

import re
from pathlib import Path

from ....state import thresholds
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
# Fresh-COLD reconverge passes (beyond the first): the warm `--resume` retries
# inside ONE run_lsp_edit_loop can wedge on a complex file and return a
# best-effort version with residual warnings; a fresh cold spawn (new session,
# re-seeded from the greenest version so far) is what actually drives them to
# zero. Re-cold this many extra times BEFORE the caller pays a whole-file
# cleanup retry (mark→decide re-run) just to give audit one fresh spawn
# (residue 2026-06-18: cleanup re-ran the full ~40min file pipeline only to
# hand audit a fresh session that then converged).
_AUDIT_RECONVERGE_PASSES = 2

_FENCE_MSG = ("the import block and the `namespace` lines must stay EXACTLY as "
              "in the original (imports are the decide stage's job; "
              "namespace-mount is out of scope) — restore them")
_FROZEN_MSG = ("`{decl}` is a FROZEN declaration — it is the problem's canonical "
               "definition (from its Defs.lean) and must be reproduced "
               "byte-for-byte. You may add a docstring ABOVE it, but do not "
               "rename, reformat, or rewrite the declaration itself — restore it "
               "exactly as in the original.")
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


def _library_name_index(conn, exclude_rel: str) -> "dict[str, list[str]]":
    """Leaf decl name -> Library paths declaring it (excluding `exclude_rel`).
    Lets the audit agent enforce the no-cross-library-collision rule inline
    instead of scanning every Library file (agent_feedback C4-B). v18: from
    `library_decls` placed rows (ALL problems, bridged or mid-harvest —
    wider than the old INDEX.md parse, which went silently EMPTY when the
    file was missing and reported "no clashes" on a real duplicate).
    conn=None (unit tests without a DB) → empty, the old missing-file
    behavior."""
    out: "dict[str, list[str]]" = {}
    if conn is None:
        return out
    for r in conn.execute(
            "SELECT target_name, slug, target_file FROM library_decls"
            " WHERE lifecycle IN ('migrated','cleaned')"
            " AND target_file IS NOT NULL"):
        path = str(r["target_file"])
        if path == exclude_rel:
            continue
        fqn = str(r["target_name"] or r["slug"])
        out.setdefault(fqn.rsplit(".", 1)[-1], []).append(path)
    return out


def _audit_context(workspace: Path, problem: str, rel: str,
                   decl_names: "list[str]", conn=None) -> str:
    """Per-file context (cold spawn) for the audit agent: module, declarations,
    a cross-library name-clash check, and the verbatim file. Retry feedback
    (gate violation / residual warnings) flows through
    `run_with_session_retries`' `retry_context`, not here."""
    try:
        body = (workspace / rel).read_text(encoding="utf-8")
    except OSError:
        body = ""
    lines = [
        f"# Final mathlib review — {problem} — `{rel}`", "",
        f"Module: `{C._mod_of_rel(rel)}`.",
        f"Declarations: {', '.join(decl_names) or '(none)'}", "",
    ]
    # Cross-library name check (agent_feedback C4-B): surface any of this
    # file's decls whose leaf name is already declared elsewhere in the
    # Library so the agent can enforce the no-collision rule without scanning
    # every file. A duplicate FQN fails the build with `environment already
    # contains` (the residue_thm `Complex.residue` clash); a same-leaf but
    # distinct-FQN name is fine.
    name_index = _library_name_index(conn, rel)
    clashes = [(d, name_index[d]) for d in decl_names if d in name_index]
    if clashes:
        lines.append("## ⚠️ Cross-library leaf-name clashes — verify the full "
                     "name differs, else rename (a duplicate FQN fails the "
                     "build with `environment already contains`)")
        for d, paths in clashes:
            lines.append(f"- `{d}` also declared in: "
                         + ", ".join(f"`{p}`" for p in paths))
        lines.append("")
    else:
        lines.append("Cross-library name check: no leaf-name clashes with "
                     "existing Library decls (grep `Library/` to confirm "
                     "when renaming).")
        lines.append("")
    lines += ["## Current file", "", "```lean", body.rstrip(), "```", ""]
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

def _decl_src(text: str, name: str) -> str:
    """Whitespace-normalized source of decl `name` (its header+body span), for
    the frozen-Defs equality check. Empty if not found."""
    from .mechanical import _decl_line_spans
    spans = _decl_line_spans(text, {name})
    if not spans:
        return ""
    lines = text.split("\n")
    return " ".join(" ".join(lines[i - 1] for i in sorted(spans)).split())


def _audit_gate(workspace: Path, target_file: str,
                decls_in_file: "list[_Decl]", *, original: str, new_text: str,
                renames_raw: "str | None", base_types: "dict[str, str]",
                scope: "list[_Decl]", pool: "list[_Decl]",
                session_token: "str | None" = None,
                frozen: "set[str] | None" = None
                ) -> "tuple[str, str, dict[str, str], list[str]]":
    """Validate the agent's `audited.lean` candidate. Returns
    `(status, detail, applied_renames, warns)` where status is one of:
      - `noop`   — identical to the original (already PR-ready), no renames
      - `fence`  — import / namespace fence violated
      - `frozen` — a Defs-origin (frozen) decl's source was modified
      - `build`  — the rewrite does not typecheck
      - `type`   — a declaration's elaborated type drifted (beyond declared rename)
      - `ok`     — green, type-safe, ZERO warnings
      - `warn`   — green, type-safe, but residual warnings remain
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
    # FREEZE: a Defs-origin decl is the problem's canonical definition (migrate
    # Gate D pinned it def-eq) — audit may add a docstring ABOVE it but must
    # reproduce the declaration itself byte-for-byte. The type gate below catches
    # rename/delete/type-drift, but a `def` BODY reformat keeps the same #check
    # type, so it needs this source-equality check. (rename/simplify/decide of
    # Defs decls are already prevented upstream; this guards the audit free-form
    # rewrite.)
    for nm in sorted((frozen or set()) & own_leaves):
        if _decl_src(new_text, nm) != _decl_src(original, nm):
            return ("frozen", _FROZEN_MSG.format(decl=nm), {}, [])
    # expected post-rename identity + type of every decl (+ nominal ctors:
    # a renamed class carries its ctor along, `Mod.New.mk`)
    leaf_map = {d.name: renames.get(d.name, d.name) for d in decls_in_file}
    pairs = [(d.name, d.fqn, f"{module}.{leaf_map[d.name]}")
             for d in decls_in_file]
    pairs += [(f"{d.name}.{c}", f"{d.fqn}.{c}",
               f"{module}.{leaf_map[d.name]}.{c}")
              for d in decls_in_file for c in ctors[d.name]]
    fqns_after = [after for _, _, after in pairs]
    # COLD type-capture (no session_token): MUST match the cold baseline
    # `base_types`. A warm LSP `#check` capture pretty-prints complex types
    # differently → spurious type-drift on every candidate → infinite reconverge
    # (#35 stage-2 regression, reverted). The warm WARNINGS gate below is safe
    # (it counts warnings, not a base-vs-candidate snapshot comparison).
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
        C._build_for_warnings(workspace, new_text, prefix="_audit_warn",
                              session_token=session_token)[1])
    return ("ok" if not warns else "warn"), "", applied, warns


def file_cleanup_audit(workspace: Path, problem: str, target_file: str,
                       decls_in_file: "list[_Decl]", *,
                       scope: "list[_Decl]", pool: "list[_Decl]",
                       conn=None, pipeline_id: "str | None" = None,
                       max_retries: int = _AUDIT_MAX_RETRIES,
                       frozen: "set[str] | None" = None
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
    decl_names = [d.name for d in decls_in_file]

    # (warns, text, renames-relative-to-`original`) of the greenest version seen
    # across reconverge passes. `original` + `base_types` stay FIXED — every
    # pass's type-invariance gate compares against the file's entry contract, no
    # matter which (improved) seed it built from.
    best: "tuple[int, str, dict[str, str]] | None" = None
    cap: "dict[str, bool]" = {}

    def _chain(prev: "dict[str, str]", new: "dict[str, str]") -> "dict[str, str]":
        # Collapse a rename chain across passes: prev {orig→cur} then new
        # {cur→next} → {orig→next} (mirror of run_staged_cleanup_file's
        # decide∘audit collapse), so the returned renames are relative to the
        # file as audit first received it, single-hop, for deferred-rewire.
        inv = {v: k for k, v in prev.items()}
        out = dict(prev)
        for o, n in new.items():
            out[inv.get(o, o)] = n
        return out

    for _pass in range(_AUDIT_RECONVERGE_PASSES + 1):
        # Each pass is a FRESH cold session (own pid/attempts) re-seeded from the
        # greenest version so far — `_pass==0` from `original`, later passes from
        # `best` (retain prior progress, like the whole-file retry's audit seed).
        seed_text = best[1] if best is not None else original
        pass_pid = pid if _pass == 0 else f"{pid}-r{_pass}"
        attempts = agent.attempts_dir_for(workspace, pass_pid)
        audited = attempts / _AUDIT_OUTPUT
        renames_file = attempts / _AUDIT_RENAMES
        pass_best: "tuple[int, str, dict[str, str]] | None" = None

        def cold_prep(ctx: SpawnCtx, _seed=seed_text, _aud=audited,
                      _rf=renames_file) -> None:
            # Seed audited.lean = the pass's seed + write Context.md; the agent
            # EDITS audited.lean in place via LSP. Warm retries within this pass
            # keep the agent's last audited.lean (incremental, --resume), so
            # cold_prep runs on cold only.
            (ctx.attempts_dir / "Context.md").write_text(
                _audit_context(workspace, problem, target_file, decl_names,
                               conn=conn),
                encoding="utf-8")
            _aud.write_text(_seed, encoding="utf-8")
            if _rf.exists():
                _rf.unlink()

        def parse(_aud=audited, _rf=renames_file, _att=attempts) -> PipelineResult:
            nonlocal pass_best
            if not _aud.exists():
                return PipelineResult(
                    outcome="failed", failure_reason="agent_no_output",
                    failure_detail=f"audit {leaf}: no {_AUDIT_OUTPUT}")
            new_text = _aud.read_text(encoding="utf-8")
            renames_raw = (_rf.read_text(encoding="utf-8")
                           if _rf.exists() else None)
            # Reuse the agent's OWN warm claimed slot for the whole-file warnings
            # gate: audited.lean's import closure is already loaded there, so the
            # gate is a ~4-5s body re-elaborate vs a fresh cold lake build. The
            # session is alive through parse_fn (run_lsp_edit_loop releases it
            # only after the loop). token absent → the gate runs cold (#35). The
            # #check type gate stays cold regardless (json stream — _verify_source
            # only takes the warm path for non-json whole-file content).
            _tok = None
            _tokf = _att / "_gateway_session.token"
            if _tokf.exists():
                try:
                    _tok = _tokf.read_text(encoding="utf-8").strip() or None
                except OSError:
                    _tok = None
            status, detail, applied, warns = _audit_gate(
                workspace, target_file, decls_in_file, original=original,
                new_text=new_text, renames_raw=renames_raw,
                base_types=base_types, scope=scope, pool=pool, session_token=_tok,
                frozen=frozen)
            if status == "noop":
                cap["noop"] = True
                return PipelineResult(outcome="success")
            if status in ("fence", "frozen", "build", "type"):
                # Non-terminal: feed the diff back as retry_context and re-spawn.
                return PipelineResult(
                    outcome="failed", failure_reason="librarian_gate_failed",
                    failure_detail=detail)
            # ok / warn — track the greenest version seen WITHIN this pass.
            if pass_best is None or len(warns) < pass_best[0]:
                pass_best = (len(warns), new_text, applied)
            if status == "ok":
                return PipelineResult(outcome="success")
            return PipelineResult(
                outcome="failed", failure_reason="librarian_warnings_remain",
                failure_detail=_WARN_MSG + "\n".join(warns[:10]))

        def feedback(sid: str, result: "PipelineResult", _att=attempts) -> None:
            _feedback.attempt_feedback(
                kind="cleanup:audit", sid=sid, slug=leaf,
                outcome=("success" if result.outcome == "success"
                         else "exhausted"),
                problem_dir=problem_dir, attempts_dir=_att, workspace=workspace)

        # `release_session_after=True`: free this audit's gateway slot before the
        # next file (or next pass) registers (the cleanup chain runs back-to-back).
        run_lsp_edit_loop(
            conn=conn, goal_id=None, pipeline_id=pass_pid,
            budget_threshold=max_retries + 1,
            shelve_threshold=thresholds.SHELVE_THRESHOLD,
            attempts_dir=attempts, workspace=workspace,
            problem=problem, problem_dir=problem_dir,
            kind="librarian", prompt_path=prompt_path, target=audited,
            cold_prep_fn=cold_prep, parse_fn=parse,
            feedback_fn=feedback, release_session_after=True)

        if pass_best is not None:
            cum = _chain(best[2] if best is not None else {}, pass_best[2])
            if best is None or pass_best[0] < best[0]:
                best = (pass_best[0], pass_best[1], cum)
        if best is not None and best[0] == 0:
            break                                  # converged: zero warnings
        if cap.get("noop") and best is None:
            break                                  # agent made no change at all

    if best is None:
        if not cap.get("noop"):
            print(f"[staged] audit `{leaf}` — kept original (no green audit in "
                  f"{_AUDIT_RECONVERGE_PASSES + 1} cold pass(es))", flush=True)
        return {}, False                          # noop or no green candidate
    n_warn, text, applied = best
    (workspace / target_file).write_text(text, encoding="utf-8")
    print(f"[staged] audit `{leaf}` — applied ({n_warn} residual warning(s), "
          f"{len(applied)} renamed"
          + (": " + ", ".join(f"{o.rsplit('.', 1)[-1]}→{n.rsplit('.', 1)[-1]}"
                              for o, n in applied.items()) if applied else "")
          + f", {C.diff_magnitude(original, text)})", flush=True)
    return applied, True
