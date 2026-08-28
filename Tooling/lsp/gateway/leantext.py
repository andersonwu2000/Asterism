"""Lean text mechanics — the compilation unit every tool elaborates.

Split out of `gateway.py` 2026-08-29 (A1-4a) unchanged: diagnostic
formatting and repeat-folding, the metaprogramming gate's readable
form, the framework import / `open` injection mirrors, sibling-stub
collection, toposort and inlining, the merged unit with its line_map in
both directions, the parity verdict, the diagnostic remap back to the
agent's frame, the goal readers, the buffer/disk resync and the
scope-balance counter.

A leaf inside this package: it imports `.state` and the
`state.assemble` / `state.db` / `state.intent` / `state.metaprog` SoT
primitives, and nothing else from here. That is what let the earlier
cuts' two call-time reach-backs close — `governor` and `sessions` now
import `_compilation_for` from HERE at module level, and its patch
target moves with it to `gateway.leantext`.

`_DECL_SLUG_RE_TMPL`, `_needed_imports`, `_proved_sibling_import_lines`
and the two `_SCOPE_*` regexes do not re-export: their only consumers
are in this file, so a facade patch would go vacuous and an
AttributeError is the better answer.
"""
from __future__ import annotations

import re
from pathlib import Path

from ...state import assemble, db, metaprog
from ...state import intent as intent_mod
from .state import SessionMetadata, _log_for, _state


# ─── Diag + import helpers ─────────────────────────

def _format_diag(d: dict) -> dict:
    rng = d.get("range") or {}
    start = rng.get("start") or {}
    sev_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}
    return {
        "line": (start.get("line", 0) or 0) + 1,
        "col": start.get("character", 0) or 0,
        "severity": sev_map.get(d.get("severity", 0), str(d.get("severity"))),
        "message": d.get("message", ""),
    }


def _collapse_repeats(formatted: "list[dict]") -> "list[dict]":
    """Fold diagnostics that repeat the same message verbatim into one
    entry carrying `repeats` + `also_lines`. Nothing is hidden — the
    payload is the same information at one tenth the reading cost
    (07-29 feedback: three identical `push_neg` deprecation warnings on
    every probe, competing with the real ok/error signal)."""
    out: "list[dict]" = []
    seen: "dict[tuple[str, str], dict]" = {}
    for f in formatted:
        key = (str(f.get("severity")), str(f.get("message")))
        first = seen.get(key)
        if first is None:
            seen[key] = f
            out.append(f)
            continue
        first["repeats"] = int(first.get("repeats", 1)) + 1
        first.setdefault("also_lines", []).append(f.get("line"))
    return out


def _metaprog_error(text: str, where: str) -> "str | None":
    """Readable form of the metaprogramming gate (`state.metaprog`), or
    None when `text` is clean.

    Every gateway path that hands agent text to Lean calls this FIRST.
    The hard backstop lives one layer down in `client._guard_
    metaprogramming` (raised from `did_open`/`did_change_full`, so no
    elaboration can happen without a scan at all); these call sites exist
    to turn that into an answer the agent can act on — being stopped is a
    teaching moment, not a stack trace. `tests/test_metaprog_guard.py`
    pins both layers.

    Why the gateway and not only the commit gate: elab-time code runs
    with the FRAMEWORK's privileges the moment a tool touches the file —
    the danger is being elaborated, not being committed, and every
    in-spawn tool elaborates long before any commit gate looks.
    """
    token = metaprog.scan_metaprogramming(text)
    if token is None:
        return None
    return metaprog.blocked_detail(token, where=where)


def _needed_imports(content: str, problem: str, workspace: Path) -> list[str]:
    """Single impl in `state.assemble` — the SAME function the commit paths
    run (task #5 Step A: no more hand-mirroring of the pipeline's injection
    rules). Used by `_ensure_imports` and the sibling-inlining path (which
    hoists these into the merged import block)."""
    return assemble.needed_framework_imports(
        content, problem=problem, workspace=workspace)


def _ensure_imports(content: str, problem: str, workspace: Path) -> str:
    """Single impl in `state.assemble` (= commit's `_ensure_imports_subgoal`)."""
    return assemble.ensure_framework_imports(
        content, problem=problem, workspace=workspace)


def _inline_sibling_stubs(
    content: str, sibling_texts: "list[str]", extra_imports: "list[str]",
    opens: "list[str]" = (),
) -> "tuple[str, list[int | None]]":
    """Build a single elaboration unit where sibling stub declarations
    precede `content`, so `<slug>` citations to freshly-declared sibling
    sub-goals resolve. Those `new_<slug>.lean` stubs live in the spawn's
    attempts dir — off the lake source path — so they cannot be imported
    pre-commit (the framework only appends their imports at commit time);
    an agent assembling the final linked patch.lean therefore can't verify
    citation arg-order / arity until after submit (agent_feedback T3).

    Lean requires every `import` at the top of the file, so all import
    lines (the siblings' own, plus `extra_imports` = the Mathlib/Defs the
    framework would inject) are hoisted and de-duped; the siblings' bodies
    (`namespace … theorem <slug> … := by sorry … end` — re-opening the
    same namespace is legal) are placed before `content`'s body.

    Returns `(merged, line_map)` where `line_map[i]` is the 1-indexed line
    of the ORIGINAL `content` that merged line `i + 1` corresponds to, or
    `None` for a framework / sibling-stub line. A hoisted import that the
    AGENT wrote keeps its original line number (a bad `import` line is the
    agent's own diagnostic, not sibling noise). The caller remaps
    diagnostics back to the agent's content frame and tags / drops the
    sibling-region ones, so line numbers stay meaningful (it must NOT
    reintroduce the very buffer/line desync T1 just fixed).

    Each sibling block is wrapped in an anonymous `section … end`: a
    stub's file-scope `open`/`variable` commands are module-local after
    commit (`import` does not propagate them), so letting them leak into
    later siblings / `content` in the single unit was a false-green class
    — content leaning on a sibling's `open` validated green here and died
    at the post-commit lake build. Declarations are unaffected by
    `section`, so citations still resolve."""
    all_imports: "list[tuple[str, int | None]]" = []  # (line, content origin)

    def _add_import(line: str, origin: "int | None" = None) -> None:
        for i, (ln, org) in enumerate(all_imports):
            if ln == line:
                if org is None and origin is not None:
                    all_imports[i] = (ln, origin)
                return
        all_imports.append((line, origin))

    for imp in extra_imports:
        _add_import(imp)

    # content: hoist its imports (keeping their original line numbers),
    # keep the body with a back-map to the agent's 1-indexed lines.
    content_body: list[tuple[str, int]] = []
    for idx, ln in enumerate(content.split("\n")):
        if ln.startswith("import "):
            _add_import(ln, idx + 1)
        else:
            content_body.append((ln, idx + 1))

    sib_body: list[str] = []
    for text in sibling_texts:
        block: list[str] = []
        for ln in text.split("\n"):
            if ln.startswith("import "):
                _add_import(ln)
            else:
                block.append(ln)
        sib_body.append("section")
        sib_body.extend(block)
        sib_body.append("end")
        sib_body.append("")  # blank line between sibling blocks

    merged: list[str] = []
    line_map: list[int | None] = []
    for imp, origin in all_imports:
        merged.append(imp)
        line_map.append(origin)
    merged.append("")
    line_map.append(None)
    # File-level `open`s (from Defs.lean) belong above any `namespace`, so
    # they sit between the hoisted imports and the sibling/content bodies.
    # All map to None — they are framework prefix, not the agent's content.
    for op in opens:
        merged.append(op if op.startswith("open ") else f"open {op}")
        line_map.append(None)
    if opens:
        merged.append("")
        line_map.append(None)
    for ln in sib_body:
        merged.append(ln)
        line_map.append(None)
    if sib_body:
        merged.append("")
        line_map.append(None)
    for ln, orig in content_body:
        merged.append(ln)
        line_map.append(orig)
    # Terminating newline: without it, Lean's end-of-input pseudo-command
    # starts at the END of the last line and Mathlib's
    # `linter.style.whitespace` fires the ghost "'' starts on column N"
    # warning on the candidate's `end` line — reported by every proving
    # agent, every day (~25 feedback entries).
    return "\n".join(merged) + "\n", line_map


# Declaration of `<slug>` in the candidate itself — so validating a
# standalone `new_<slug>.lean` stub inlines nothing (it declares its own
# slug), and we never inline a sibling the content already defines.
_DECL_SLUG_RE_TMPL = (
    r"(?m)^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
    r"(?:noncomputable[ \t]+|private[ \t]+|protected[ \t]+|scoped[ \t]+)*"
    r"(?:theorem|lemma|def|structure|class|abbrev)[ \t]+{slug}\b")


def _collect_referenced_sibling_stubs(
    attempts_dir: Path, content: str, own_name: "str | None" = None,
) -> "list[tuple[str, str]]":
    """Sibling `new_<slug>.lean` stubs in `attempts_dir` that `content`
    REFERENCES (uses `<slug>` as an identifier) but does NOT itself
    declare — computed to a FIXPOINT: a collected stub's own references
    pull further stubs in (D-lite: a stub B referenced only by stub A used
    to be absent from the unit, so A's citation of B silently vanished
    from the probe instead of resolving or erroring). Excludes the stub
    being validated and any already inlined, so validating a standalone
    stub (which references no sibling) inlines nothing and the common case
    stays the plain `_ensure_imports` path."""
    out: list[tuple[str, str]] = []
    try:
        stubs = sorted(attempts_dir.glob("new_*.lean"))
    except OSError:
        return out
    texts: "dict[str, str]" = {}
    for stub in stubs:
        # THE SESSION'S OWN TARGET IS NOT A SIBLING, and file identity is
        # the only test that says so for every seat. The decl-name guard
        # below ("does `content` declare `<slug>`") holds for Backward,
        # whose stub file and theorem share a name — and never for
        # Forward, whose target is `new_forward.lean` while its theorem
        # is whatever the agent invented. So the target's DISK copy was
        # inlined ahead of the live content, the unit carried the
        # declaration twice, and the tools reported "has already been
        # declared" against the very line the agent had just written.
        # Latent since 2026-06-18; 45 reports on 08-13/14 alone, all
        # Forward, none Backward. The reference test that let it in is a
        # bare word match over the whole text INCLUDING COMMENTS, and
        # the word came from the framework's own seed scaffold
        # (`pipeline/forward.py`: "-- Write ONE forward lemma here").
        if own_name is not None and stub.name == own_name:
            continue
        slug = stub.stem[len("new_"):]
        if not slug:
            continue
        try:
            texts[slug] = stub.read_text(encoding="utf-8")
        except OSError:
            continue
    collected: "dict[str, str]" = {}
    frontier = [content]
    while frontier:
        scan = frontier.pop()
        for slug, text in texts.items():
            if slug in collected:
                continue
            if re.search(_DECL_SLUG_RE_TMPL.format(slug=re.escape(slug)),
                         content):
                continue  # content declares it (the stub itself / inlined)
            if not re.search(rf"\b{re.escape(slug)}\b", scan):
                continue  # not referenced by this text
            collected[slug] = text
            frontier.append(text)
    # deterministic order (glob order) for stable units
    return [(s, texts[s]) for s in texts if s in collected]


def _toposort_siblings(
    siblings: "list[tuple[str, str]]",
) -> "list[tuple[str, str]]":
    """Order `(slug, text)` sibling stubs so each appears AFTER every other
    sibling whose slug its body references — Lean needs a declaration before
    its use, but `_collect_referenced_sibling_stubs` returns glob
    (alphabetical) order, breaking inter-sibling citations (agent_feedback:
    "inlining sub-goal stubs ... yields a spurious unknown-identifier
    forward-reference"). Stable among independents; a dependency cycle
    (shouldn't occur for sorry-stubs) degrades to input order rather than
    dropping any stub."""
    texts = dict(siblings)
    all_slugs = [s for s, _ in siblings]
    deps: "dict[str, set]" = {}
    for slug, text in siblings:
        deps[slug] = {o for o in all_slugs
                      if o != slug
                      and re.search(rf"\b{re.escape(o)}\b", text)}
    ordered: "list[str]" = []
    placed: set = set()
    remaining = list(all_slugs)
    while remaining:
        ready = [s for s in remaining if deps[s] <= placed]
        if not ready:  # cycle — emit the rest in input order, drop nobody
            ordered.extend(remaining)
            break
        for s in ready:
            ordered.append(s)
            placed.add(s)
        remaining = [s for s in remaining if s not in placed]
    return [(s, texts[s]) for s in ordered]


def _harvest_open_lines(text: str) -> "list[str]":
    """Single impl in `state.assemble.harvest_open_lines` (task #5 Step B).
    Carries the agent's working-patch opens into validate_file's compilation
    unit so a probed sub-goal stub elaborates against the SAME open
    namespaces the committed file will — and since Step B the commit side
    carries them too (`assemble_for_commit(carry_opens=…)`)."""
    return assemble.harvest_open_lines(text)


def _merge_opens(content: str, defs_opens: "list[str]",
                 extra_opens: "list[str]") -> "list[str]":
    """Prefix opens for the compilation unit: Defs.lean's file-scope opens
    (raw args, per `intent_mod.defs_opens`) plus `extra_opens` (the session
    patch's own `open ...` lines), each normalized to a full `open ...`
    line, de-duped, and dropping any already present verbatim in `content`
    (so probing the patch itself never doubles its opens)."""
    have = set(_harvest_open_lines(content))
    out: "list[str]" = []
    for o in list(defs_opens) + list(extra_opens):
        line = o if o.startswith("open ") else f"open {o}"
        if line in have or line in out:
            continue
        out.append(line)
    return out


def _proved_sibling_import_lines(
    texts: "list[str]", problem: str, workspace: "Path",
    declared: "set[str]",
) -> "list[str]":
    """The `import Problems.<p>.proofs.L_<slug>` lines the commit-side
    `assemble_for_commit` will auto-inject (proved-sibling auto-fix) for any
    of `texts` — hoisted into the unit's import block instead of mutated
    into the content, so the agent's line numbers (line_map) are untouched
    (task #5 Step C: the probe resolves the same modules commit will,
    killing the false-RED where validate said `unknown identifier` on a
    reference commit would have auto-imported). Best-effort mirror of the
    commit behavior: no DB on disk / any failure → [] (validate must never
    break on this)."""
    db_path = workspace / "asterism.db"
    if not db_path.exists():
        return []
    try:
        conn = db.connect(db_path)
    except Exception:
        return []
    try:
        out: "list[str]" = []
        for t in texts:
            _, added = assemble.inject_sibling_imports(
                conn, t, problem=problem, declared_slugs=declared)
            for s in added:
                line = f"import Problems.{problem}.proofs.L_{s}"
                if line not in out:
                    out.append(line)
        return out
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _parity_for(
    content: str, problem: str, workspace: "Path", inlined_slugs: "list[str]",
    header: "dict", goal_id: "int | None" = None,
) -> "dict":
    """Does the sandbox's verdict cover what the real build will see?

    The two units are NOT the same object and never can be: the sandbox
    INLINES a referenced sibling's stub so it can elaborate without that
    sibling being built, while commit gives the sibling its own module and
    an `import` line. So comparing unit digests would alarm on every call.
    What must agree is narrower and checkable — every name the sandbox
    resolved through an inlined stub has to be a name the real build can
    resolve too:

      exact       every inlined sibling is PROVED, and commit imports it.
                  The sandbox saw the same declarations lake will.
      conditional at least one inlined sibling is not proved yet, so the
                  sandbox elaborated against `:= by sorry` and the real
                  build will use whatever that goal eventually becomes.
                  Legitimate and common (that is how a batch works) — but
                  it is NOT the same green, and it must not render as one.
      unresolved  an inlined sibling is neither proved nor a declared stub
                  of this batch, and no commit import covers it. That is a
                  framework defect, not the agent's: the probe answered a
                  question the build was never going to be asked.

    This is the handshake #179 needed. That bug hid for a week because
    the divergence surfaced to the AGENT as `Unknown identifier`, which
    reads as "my sibling does not exist" — 37 reports, several saying
    plainly they could not tell that from "wrong approach". A named
    parity verdict costs one field and moves the diagnosis to the side
    that can act on it."""
    if not inlined_slugs:
        return {"state": "exact", "note": "no siblings inlined"}
    # EXACT module identity, never substring: `"L_foo" in imports` (a
    # space-joined string) matched `L_foobar`'s import and marked an
    # unproved sibling proved (feedback 2026-08-25, soundness-adjacent
    # missignal — the kernel gates still held, the AGENT was misled).
    import_names = set(header.get("imports") or ())

    def _import_covers(slug: str) -> bool:
        mod = f"L_{slug}"
        return any(imp == mod or imp.endswith(f".{mod}")
                   for imp in import_names)
    proved: "list[str]" = []
    conditional: "list[str]" = []
    unresolved: "list[str]" = []
    db_path = workspace / "asterism.db"
    statuses: "dict[str, str]" = {}
    if db_path.exists():
        try:
            conn = db.connect(db_path)
            try:
                for slug in inlined_slugs:
                    row = conn.execute(
                        "SELECT status FROM goals WHERE problem = ? "
                        "AND slug = ?", (problem, slug)).fetchone()
                    if row is not None:
                        statuses[slug] = str(row[0])
            finally:
                conn.close()
        except Exception:  # noqa: BLE001 — parity must never break validate
            statuses = {}
    for slug in inlined_slugs:
        st = statuses.get(slug)
        if st == "proved":
            proved.append(slug)
        elif st is not None:
            conditional.append(slug)
        elif _import_covers(slug):
            proved.append(slug)
        else:
            unresolved.append(slug)
    # Commit's strict-ancestor cycle predicate, mirrored (2026-08-26,
    # feedback x2: validate said "citation ok", commit rejected the
    # circularity). Same walk, same SQL home (`db.strict_ancestor_ids`).
    cycle_slugs: "list[str]" = []
    if goal_id is not None and db_path.exists():
        try:
            conn = db.connect(db_path)
            try:
                anc = db.strict_ancestor_ids(conn, int(goal_id))
                for slug in inlined_slugs:
                    row = conn.execute(
                        "SELECT id FROM goals WHERE problem = ? "
                        "AND slug = ?", (problem, slug)).fetchone()
                    if row is not None and int(row[0]) in anc:
                        cycle_slugs.append(slug)
            finally:
                conn.close()
        except Exception:  # noqa: BLE001 — parity must never break validate
            cycle_slugs = []
    if unresolved:
        out = {
            "state": "unresolved",
            "framework_parity_error": sorted(unresolved),
            "note": ("the probe resolved these through an inlined stub, but "
                     "the commit unit neither imports them nor knows them as "
                     "goals — your mathematics was not judged against what "
                     "will be built. Report this; it is not your error."),
        }
    elif conditional:
        out = {
            "state": "conditional",
            "depends_on": sorted(conditional),
            "note": ("elaborated against the DECLARED signature of these "
                     "not-yet-proved siblings; the real build uses whatever "
                     "they become. A clean result here is conditional on "
                     "them proving as declared."),
        }
    else:
        out = {"state": "exact", "proved_siblings": sorted(proved)}
    if cycle_slugs:
        out["ancestor_cycle"] = sorted(cycle_slugs)
        out["ancestor_cycle_note"] = (
            "commit WILL reject this: the cited sibling(s) above are "
            "strict ANCESTORS of your goal — the ancestor depends on "
            "your goal, so citing it is circular. Prove the goal without "
            "them, or decompose into genuinely new sub-goals.")
    return out


def _build_compilation_unit(
    content: str, problem: str, workspace: "Path", attempts_dir: "Path",
    extra_opens: "list[str]" = (), own_name: "str | None" = None,
) -> "tuple[str, list[int | None], list[str]]":
    """The SINGLE compilation state every in-spawn LSP tool elaborates:
    framework imports + commit's proved-sibling auto-imports + `Defs.lean`
    file-level opens + referenced `new_<slug>.lean` sibling stubs
    (topologically ordered) + `content`. Since task #5 Step C the unit is
    derived from the SAME `state.assemble` primitives the commit paths run,
    so what the probe elaborates is what commit will land (modulo the
    single-unit fold itself).

    Returns `(merged, line_map, inlined_slugs)`. `line_map[i]` maps merged
    line `i + 1` back to `content`'s 1-indexed line, or `None` for a
    framework-prefix / sibling-region line — so callers translate tool
    inputs (`content` frame → merged frame) and diagnostics (merged frame →
    `content` frame) through one map, killing the prior split where
    `apply_edit`/`goal_at`/`errors_at` saw a sibling-less buffer while
    `validate_file` synthesized a different one. Always returns a real
    `line_map` (even with no siblings: imports + opens are still prefix), so
    every tool remaps uniformly."""
    siblings = _toposort_siblings(
        _collect_referenced_sibling_stubs(attempts_dir, content,
                                          own_name))
    sib_texts = [t for _, t in siblings]
    declared = {s for s, _ in siblings}
    merged, line_map = _inline_sibling_stubs(
        content,
        sib_texts,
        _needed_imports(content, problem, workspace)
        + _proved_sibling_import_lines(
            [content] + sib_texts, problem, workspace, declared),
        # Defs' own namespace rides along with its opens: a bare snippet
        # (no `namespace Problems.…` wrapper) then resolves Defs symbols
        # the way the committed wrapped file does; redundant-but-harmless
        # for content that carries the wrapper (07-18 ×3 + 07-19 ×9).
        opens=_merge_opens(content,
                           intent_mod.defs_opens(workspace, problem)
                           + intent_mod.defs_namespaces(workspace, problem),
                           list(extra_opens)),
    )
    return merged, line_map, [s for s, _ in siblings]


def _commit_header_for(
    content: str, problem: str, workspace: "Path", attempts_dir: "Path",
    extra_opens: "list[str]" = (),
) -> "dict":
    """The exact header lines the framework itself will inject into THIS
    content at commit — `assemble_for_commit`'s framework imports +
    proved-sibling imports + Defs/carried opens, plus the mechanically
    injected intra-batch import edges (task #84, same
    `referenced_batch_slugs` scan the commit side runs). Surfaced in
    validate_file's response so the agent SEES the wrapping (and knows
    not to hand-write it); these lines are already part of the probe's
    compilation unit. Best-effort — a failed sub-derivation just leaves
    its lines out (validate must never break on this)."""
    all_stub_slugs: "list[str]" = []
    try:
        for stub in sorted(attempts_dir.glob("new_*.lean")):
            slug = stub.stem[len("new_"):]
            if slug:
                all_stub_slugs.append(slug)
    except OSError:
        pass
    # batch edges: only slugs content does not itself declare (validating
    # the stub itself must not predict a self-import)
    candidates = [
        s for s in all_stub_slugs
        if not re.search(_DECL_SLUG_RE_TMPL.format(slug=re.escape(s)),
                         content)]
    batch_imports = [
        f"import Problems.{problem}.proofs.L_{s}"
        for s in assemble.referenced_batch_slugs(content, candidates)]
    imports = (
        _needed_imports(content, problem, workspace)
        + batch_imports
        + _proved_sibling_import_lines(
            [content], problem, workspace, set(all_stub_slugs)))
    opens = _merge_opens(content, intent_mod.defs_opens(workspace, problem),
                         list(extra_opens))
    return {"imports": imports, "opens": opens}


def _merged_line_for(
    line_map: "list[int | None] | None", content_line: int,
) -> int:
    """Forward map: a 1-indexed `content_line` (the frame the agent's tool
    args use) → its 1-indexed line in the merged compilation unit. Inverse
    of `line_map` (which is merged → content). Falls back to `content_line`
    unchanged when there is no map or the line isn't a mapped body line
    (e.g. a hoisted import line — tools only query theorem/tactic body
    lines, so the fallback is never hit in practice)."""
    if line_map is None:
        return content_line
    for i, orig in enumerate(line_map):
        if orig == content_line:
            return i + 1
    return content_line


def _compilation_for(meta: SessionMetadata) -> "tuple[str, list[int | None]]":
    """`meta`'s single compilation unit (session content + Defs opens +
    referenced sibling stubs) and its line_map. The one elaboration target
    every claimed-session tool swaps in, so `goal_at` / `errors_at` /
    `apply_edit` see exactly what `validate_file` (and, post-commit, lake)
    do — no more sibling-less live buffer vs synthesized validate world."""
    if meta.kind == "interactive":
        # The serve editor's buffer IS the compilation unit — no
        # framework prefix, no sibling stubs; identity line_map.
        n = meta.file_content.count("\n") + 1
        return meta.file_content, list(range(1, n + 1))
    merged, line_map, _ = _build_compilation_unit(
        meta.file_content, meta.problem, meta.workspace,
        meta.target_path.parent, own_name=meta.target_path.name)
    return merged, line_map


def _remap_inlined_diags(
    formatted: "list[dict]", line_map: "list[int | None]",
) -> "list[dict]":
    """Map each diagnostic's line from the merged elaboration unit back to
    the agent's original content frame via `line_map`. Sibling-region
    lines (`line_map` is None there): drop non-errors — the inlined
    `:= by sorry` stubs each emit a 'declaration uses sorry' warning that
    is pure noise — and tag errors so the agent knows the fault is in a
    cited sibling stub, not its own patch."""
    n = len(line_map)
    out: list[dict] = []
    for f in formatted:
        ln = f.get("line")
        if not isinstance(ln, int) or ln < 1 or ln > n:
            out.append(f)  # outside the map — leave untouched
            continue
        orig = line_map[ln - 1]
        if orig is not None:
            out.append({**f, "line": orig})
        elif f.get("severity") == "error":
            out.append({**f, "message": "[inlined sibling stub] "
                        + str(f.get("message", ""))})
        # else: sibling-region warning/info → drop as noise
    return out


def _summarize_goal(result) -> str:
    if result is None:
        # plainGoal null = position outside any proof/tactic block —
        # NOT str(None): "None" read as a goal named None (owner hit it)
        return "no goals"
    if not isinstance(result, dict):
        return str(result)
    rendered = result.get("rendered")
    if rendered:
        return rendered
    goals = result.get("goals") or []
    if goals:
        return "\n---\n".join(goals)
    return "<no goals — proof complete at this position>"


def _goal_present(result) -> bool:
    """True iff plainGoal returned a live goal (vs an empty/closed state).

    `rendered == "no goals"` is Lean's CLOSED state, not a live goal —
    it is exactly what a query at/inside/after a `sorry` returns, so
    treating that truthy string as present had silently disabled the
    B#4 sorry-fallback (goal_at answered "no goals" on a sorry line
    instead of re-querying the token start for the real goal)."""
    if not isinstance(result, dict):
        return False
    if result.get("goals"):
        return True
    rendered = result.get("rendered")
    return bool(rendered) and str(rendered).strip() != "no goals"


def _sorry_start_col(meta, line: int) -> "int | None":
    """Column (0-indexed) of the first `sorry` token on the agent's 1-indexed
    `line` (its own content frame), or None. goal_at's B#4 fallback re-queries
    here: a `sorry` admits its goal, so plainGoal is empty AT/INSIDE/AFTER the
    token but returns the live goal at its START (verified 2026-06-22)."""
    try:
        lines = meta.target_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if not (1 <= line <= len(lines)):
        return None
    m = re.search(r"\bsorry\b", lines[line - 1])
    return m.start() if m else None


def _stub_fingerprint(attempts_dir: "Path",
                      own_name: "str | None" = None) -> tuple:
    """(name, mtime_ns, size) per SIBLING `new_*.lean`, sorted — the
    sibling half of the compilation unit's identity.

    The session's own target is excluded, and that is not a detail: for
    the Forward seat the target IS a `new_*.lean`, so every `apply_edit`
    write-through moved the fingerprint, cleared the slot's ownership,
    and sent the next read down the cold path to re-elaborate the unit
    it had just elaborated. The fingerprint's job is "did a sibling
    change under me"; the target's own edits are already tracked by the
    mirror two lines below.

    OSError → () (best-effort; an unreadable dir just reads as empty)."""
    try:
        return tuple(sorted(
            (f.name, f.stat().st_mtime_ns, f.stat().st_size)
            for f in attempts_dir.glob("new_*.lean")
            if own_name is None or f.name != own_name))
    except OSError:
        return ()


def _resync_buffer_from_disk(meta: "SessionMetadata") -> "str | None":
    """Adopt the on-disk `target_path` as the source of truth for the
    in-memory `file_content` mirror before any tool reads it.

    Returns an error string when the disk read FAILED (transient lock /
    missing file) — the mirror is then possibly stale. Read-only tools
    may proceed on the stale mirror; `apply_edit` must NOT (its
    write-through would overwrite newer on-disk content with
    stale-based text — the resurrection corruption class).

    Agents edit patch.lean through the `Write` / `Edit` tools too, which
    touch disk directly and bypass apply_edit's mirror update — leaving
    `meta.file_content` stale. Every swap_in tool then didChanges that
    STALE mirror into the slot, so `errors_at` / `goal_at` report phantom
    diagnostics at line numbers that no longer exist on disk, and
    `apply_edit` computes its line splice against stale text
    (agent_feedback T1, ~12 reports — the run's highest-frequency
    friction). Disk is never staler than the mirror (apply_edit, the only
    mirror writer, writes disk in the same breath at write-through), so
    unconditionally adopting disk on mismatch is safe and makes disk the
    single source of truth."""
    # Sibling-stub freshness rides the same resync (agent_feedback #4a):
    # a stub written AFTER the last elaboration changes the merged unit;
    # invalidate slot ownership so the next acquire re-elaborates.
    fp = _stub_fingerprint(meta.target_path.parent,
                           meta.target_path.name)
    if fp != meta.stub_fingerprint:
        meta.stub_fingerprint = fp
        for _slot in _state.workers:
            if _slot.claimed_by == meta.pipeline_id:
                _slot.content_pipeline_id = None
                break
        _log_for(meta, {"event": "sibling_stub_resync", "stubs": len(fp)})

    try:
        disk = meta.target_path.read_text(encoding="utf-8")
    except OSError as e:
        return f"target file unreadable during resync: {e}"
    if disk != meta.file_content:
        meta.file_content = disk
        # Invalidate the claimed slot's content ownership: the hot path in
        # `_acquire_slot` keys "slot already has our content" on PIPELINE
        # identity, so after an external Write/Edit the refreshed mirror
        # was never didChange'd in and `errors_at`/`goal_at` reported the
        # PREVIOUS elaboration until some no-op apply_edit (~8 agent
        # reports, sphere_homology 2026-07-04/05). Clearing the marker
        # forces the next swap_in acquire through the cold_warmup
        # didChange + wait_for_diagnostics. Safe lock-free: a session's
        # tool calls are serial, so no concurrent op holds this slot.
        for _slot in _state.workers:
            if _slot.claimed_by == meta.pipeline_id:
                _slot.content_pipeline_id = None
                break
        _log_for(meta, {"event": "buffer_resync_from_disk",
                        "disk_lines": disk.count("\n") + 1})


_SCOPE_OPEN_RE = re.compile(
    # `mutual` is `end`-closed too. Without it a mutual block's `end`
    # counted as a closer with no opener and the balance went negative —
    # a false "one `end` too many" on a correct file (2026-08-10).
    r"^\s*(?:noncomputable\s+)?(?:namespace|section|mutual)\b")
_SCOPE_END_RE = re.compile(r"^\s*end\b")


def _scope_balance(text: str) -> int:
    """`namespace`/`section` openers minus `end` closers.

    Purely syntactic, which is the point: it is correct the instant the
    splice lands, whereas the elaborator's diagnostics in the same
    response may still describe the PREVIOUS version. Two agents in one
    run replaced a whole file, dropped its `end <namespace>`, and only
    learned about it a round-trip later (2026-08-02 feedback x2)."""
    opens = closes = 0
    for line in text.split("\n"):
        if _SCOPE_OPEN_RE.match(line):
            opens += 1
        elif _SCOPE_END_RE.match(line):
            closes += 1
    return opens - closes
