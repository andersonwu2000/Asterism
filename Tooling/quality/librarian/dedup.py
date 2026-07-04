"""PHASE 3 cleanup-dedup (v1a, mechanical) — see docs/archive/design/librarian_cleanup.md §7.

This module's first, riskiest piece: the **token-aware reference rewrite**.
When dedup drops a redundant decl X (survivor Y), every reference to X must
become Y. v0.2/v0.3 deferred this as "substring-rewrite risk" (relabel.py
header): a naive `text.replace("foo", "bar")` corrupts `foobar`, the tail of
a fully-qualified `A.b.foo`, and prose comments. The enabling change in v1a
is rewire-or-revert (build + Gate B after every drop → revert on any
meaning-affecting error), so the rewrite only has to be *careful*, not
provably perfect. This module keeps it careful:

  - whole-token only (identifier boundaries; `.` counts as a boundary char,
    so a bare name never matches an FQN tail / field projection, and an FQN
    never matches when extended by a further `.component`),
  - **code regions only** — references inside `--`, `/- -/`, and `/-- -/`
    comments are left verbatim (replacing a prose word that happens to equal
    a decl name would corrupt docs; comment realignment is a P4 concern).

Cross-decl references in a Library file are BARE when same-namespace (one
file), and fully-qualified `Library.<mod>.<decl>` across files (confirmed in
Library/LinearAlgebra/NormalDiagonalization/MatrixNorm.lean). Both forms go
through `replace_token` with the appropriate `old`.
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import dedupe as _dd
from .. import lake_probe as _lp
from .cleanup._common import (_BATCH_TIMEOUT_SEC, _DECL_NAME_RE, _Decl,
                              _build_decl_isolated, _build_file_copy_isolated,
                              _file_opens, _missing_oleans, _mod_of_rel,
                              _opens_in, _strip_json_fence,
                              decl_proof_body, decl_span, replace_proof,
                              replace_token)
from .cleanup.audit import file_cleanup_audit
from .cleanup.decide import file_cleanup_decide
from .cleanup.mechanical import (file_cleanup_normalize_whitespace,
                                 file_cleanup_strip_framework_comments,
                                 file_cleanup_underscore_unused_hyps,
                                 file_cleanup_unused_args)
from .cleanup.simplify import _mark_simplify_file, decl_cleanup_simplify_file


# ---------------------------------------------------------------------
# isDefEq probe — the dedup redundancy test (NOT A's apply-probe)
#
# A's `apply @Y <;> assumption` tests "X is a CONSEQUENCE of Y (+ X's own
# hypotheses)" — correct for reuse (discharge a goal), but far too loose for
# dedup: a lemma with a generic conclusion (`∀ idx, g idx = 0`) is a
# consequence of many unrelated lemmas (jordan scan: 87/93 false hits). Dedup
# must instead ask "is X the SAME statement as Y" — definitional type
# equality. Mechanised as a term-mode check: `theorem _dc : <X's ∀-type> :=
# @Y` typechecks iff `Y : X.type` up to defeq, i.e. Y can stand in for X
# everywhere (exactly the precondition for dropping X + redirecting refs→Y).
# This is task #93's "mechanical isDefEq", the conservative floor; near-dups
# that need a one-line bridge are the v1b agentic tier.
# ---------------------------------------------------------------------

# Max pairs per `lake env lean` invocation. A giant single file over-reports
# True: Lean stops elaborating past an internal error threshold, so pairs
# beyond it produce no error line and are mis-marked defeq (courant dry-run
# 2026-06-06: 23 false hits in one ~1000-pair batch; n=1/n=2 were correct).
# Chunking keeps each file small enough for reliable per-pair attribution.
_BATCH_MAX_PAIRS = 40


# Type-colon splitter (FIRST depth-0 `:`) — single source in the lower
# `dedupe` module (already imported as `_dd`). `dedupe._to_forall_form` /
# `_conclusion_of_signature` share it too; the §13 latent bug was their old
# LAST-colon scan mangling ∃/∀/fun-bearing conclusions. Aliased (not
# re-defined) so there is exactly one implementation.
_type_colon_pos = _dd._type_colon_pos


def sig_to_forall(sig: str) -> str:
    """`<binders> : <conclusion>` → `∀ <binders>, <conclusion>` (or just
    `<conclusion>` when there are no binders), splitting at the true type
    colon (`_type_colon_pos`)."""
    p = _type_colon_pos(sig)
    if p < 0:
        return sig.strip()
    binders = sig[:p].strip()
    concl = sig[p + 1:].strip()
    return f"∀ {binders}, {concl}" if binders else concl


def batch_defeq(workspace: Path, problem: str,
                pairs: list[tuple[str, str, str]]) -> list[bool]:
    """For each `(x_signature, canonical_module, canonical_fqn)`, check
    whether `theorem _dc : <∀-form of x_signature> := @canonical_fqn`
    typechecks (X.type ≡ Y.type, defeq). `x_signature` is `<binders> :
    <conclusion>` (from `dedupe._extract_full_signature`).

    Returns a bool list aligned with `pairs`. Cold `lake env lean` (same
    rationale as the apply-probe: a warm gateway is no faster on a fresh
    Mathlib-importing file — task #108). Fail-open all-False on any error.
    """
    if not pairs:
        return []

    # Chunk: a too-large single file over-reports True (see _BATCH_MAX_PAIRS).
    if len(pairs) > _BATCH_MAX_PAIRS:
        out: list[bool] = []
        for i in range(0, len(pairs), _BATCH_MAX_PAIRS):
            out.extend(batch_defeq(workspace, problem,
                                   pairs[i:i + _BATCH_MAX_PAIRS]))
        return out

    seen_modules = {mod for _, mod, _ in pairs if mod}
    missing = _missing_oleans(workspace, sorted(seen_modules))   # O1: skip warm
    if missing:
        from ...pipeline._lake import lake_build_modules
        try:
            lake_build_modules(workspace, missing)
        except Exception as exc:  # noqa: BLE001 — best-effort pre-flight
            print(f"[dedup] pre-flight lake build failed (non-fatal): {exc}",
                  flush=True)

    # NB: no `import Problems.<problem>.Defs` here — Library decls are
    # Defs-free (Gate A import-closure), and the problem's Defs olean is
    # typically unbuilt during a cleanup campaign → importing it would
    # global-error the whole probe. Library dedup needs only Mathlib + the
    # canonical Library modules.
    lines = ["import Mathlib"]
    for mod in sorted(seen_modules):
        lines.append(f"import {mod}")
    lines += ["", "namespace dedup_defeq_check", ""]

    pair_start_lines: list[int] = []
    for i, (sig, _mod, fqn) in enumerate(pairs):
        forall_ty = " ".join(sig_to_forall(sig).split())
        pair_start_lines.append(len(lines) + 1)
        if not fqn:
            lines.append(f"-- pair {i} (no fqn)")
            lines.append(f"theorem _dc_{i} : True := trivial_unknown_force_fail")
            lines.append("")
            continue
        lines.append(f"-- pair {i}")
        lines.append(f"theorem _dc_{i} : {forall_ty} := @{fqn}")
        lines.append("")
    lines.append("end dedup_defeq_check")
    content = "\n".join(lines)

    run = _lp.run_lean_source(workspace, content, prefix="_dedup_defeq",
                              timeout=_BATCH_TIMEOUT_SEC)
    if run.infra:
        # INFRA — timeout / spawn error / rc≠0 with no attributable error line —
        # is NOT a "not defeq" verdict: the probe environment is broken (commonly
        # a load-induced timeout or a stale/missing dependency olean mid-cleanup).
        # Refuse all pairs, but LOUDLY + auditable: the old silent all-False on
        # timeout masked lost dedups as "near/bridge" and made campaigns load-
        # dependent with no audit trail (Finding B; Fable-5 review).
        kind = "timeout" if run.timed_out else "probe env error"
        print(f"[dedup] batch_defeq: INFRA ({kind}, rc={run.returncode}) — "
              f"no verdict for {len(pairs)} pair(s), treated as keep; "
              f"tail: {run.output[-400:].strip()}", flush=True)
        return [False] * len(pairs)
    error_lines = run.error_lines
    if not error_lines:                  # clean build → every pair is defeq
        return [True] * len(pairs)
    in_pair = set()
    for el in error_lines:
        for i, start in enumerate(pair_start_lines):
            end = (pair_start_lines[i + 1] - 1
                   if i + 1 < len(pair_start_lines) else len(lines))
            if start <= el <= end:
                in_pair.add(el)
                break
    if error_lines - in_pair:        # error outside every pair = global env break
        # Same INFRA class (Lean attributed a line, just not to a pair block) —
        # refuse all, loudly.
        print(f"[dedup] batch_defeq: GLOBAL probe error "
              f"({len(error_lines - in_pair)} error line(s) outside pair blocks) "
              f"— refusing all {len(pairs)} pair(s); likely stale/missing olean. "
              f"tail: {run.output[-400:].strip()}", flush=True)
        return [False] * len(pairs)
    results = []
    for i, start in enumerate(pair_start_lines):
        end = (pair_start_lines[i + 1] - 1
               if i + 1 < len(pair_start_lines) else len(lines))
        results.append(not any(start <= el <= end for el in error_lines))
    return results


# ---------------------------------------------------------------------
# drop_decl — remove a dropped duplicate's text from its file
#
# Pairs with `replace_token` (which redirects refs X→Y elsewhere): once a
# decl X is deduped away, its own definition is deleted. Span = the decl's
# leading doc/comment block + the decl body, up to the next decl block (or
# `end <ns>` / EOF). Whitespace/blank-line imperfections are harmless —
# rewire-or-revert (cone build) is the correctness backstop; tidiness is a
# later (P2/P4) concern.
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# Import-cycle guard for cross-file bridges (#41)
#
# classify lays files on an ACYCLIC DAG of the ORIGINAL proof citations
# (`_merge_file_sccs` merges any usage-cycle into one file). But a dedup BRIDGE
# rewrites X's proof to `:= <cite Y>` — a NEW cross-file edge classify never saw.
# If Y's module already (transitively) imports X's module, adding `import
# Y.module` to X's file closes an import cycle → the module no longer builds. The
# per-decl isolation gate can't see it (it imports both oleans, no rebuild), so
# the cycle only surfaces at the later real-module build as a hard failure →
# retry → STALL (residue OuterHolomorphicPart ↔ InnerPrincipalPart, 2026-06-20).
# So check reachability on the on-disk import graph BEFORE applying the bridge.
# ---------------------------------------------------------------------
_LIB_IMPORT_RE = re.compile(r"^\s*import\s+(Library\.[\w.]+)", re.M)


def _lib_imports_on_disk(workspace: Path, module: str) -> "list[str]":
    """The `Library.*` modules a module's source file imports (best-effort —
    empty if the file is absent/unreadable)."""
    rel = module.replace(".", "/") + ".lean"
    try:
        return _LIB_IMPORT_RE.findall((workspace / rel).read_text(encoding="utf-8"))
    except OSError:
        return []


def _imports_reaches(workspace: Path, src: str, dst: str,
                     _memo: "dict | None" = None) -> bool:
    """Does module `src` transitively import `dst` (over Library modules)? Used
    to reject a bridge whose cited module would close an import cycle back to the
    bridging file. BFS over on-disk imports."""
    seen: set[str] = set()
    stack = [src]
    while stack:
        m = stack.pop()
        for imp in _lib_imports_on_disk(workspace, m):
            if imp == dst:
                return True
            if imp not in seen:
                seen.add(imp)
                stack.append(imp)
    return False


def drop_decl(text: str, name: str) -> "tuple[str, bool]":
    """Remove decl `name`'s block from `text`. Returns `(new_text, removed)`."""
    span = decl_span(text, name)
    if span is None:
        return text, False
    s, e = span
    return text[:s] + text[e:], True


# ---------------------------------------------------------------------
# v1a campaign — mechanical Library dedup (standalone, file + INDEX driven)
#
# Opt-in, per-problem. Operates IN-PLACE on the committed Library/ (= the
# green baseline; `git checkout` is the reset). For each scope decl X, the
# isDefEq probe (`batch_defeq`) finds a defeq twin Y in the domain pool
# (mathlib tier = v1c); the deterministic survivor rule keeps one, drops the
# other via drop_decl + replace_token (rewire), then rewire-or-revert (build
# the problem's Library modules → keep, else restore). Loops to fixpoint.
#
# v1a scope: DB-free (no verdict writes), no formal Gate-B re-derivation —
# the per-drop full build of the problem's modules is the gate (defeq drop +
# build-passes ⇒ meaning-preserving). DB verdict + Gate-B re-run + cross-
# problem rewire + LLM tiers are integration / v1b.
# ---------------------------------------------------------------------

def _mod_of_fqn(fqn: str) -> str:
    return fqn.rsplit(".", 1)[0]


def _db_index(conn) -> "dict[str, list[tuple[str, str]]]":
    """{problem: [(fqn, rel)]} over BRIDGED problems' placed decls — the
    v18 successor of parsing INDEX.md (the pool = other, already-promoted
    problems, exactly what the bridged marker means). conn=None (standalone
    campaign without a DB) → empty."""
    out: dict[str, list[tuple[str, str]]] = {}
    if conn is None:
        return out
    from ...state import db as _db
    for prob, rows in _db.bridged_library_index(conn).items():
        out[prob] = [(str(r["target_name"] or r["slug"]),
                      str(r["target_file"]))
                     for r in rows if r["target_file"] and r["target_name"]]
    return out


def _file_full_sigs(text: str) -> "dict[str, str]":
    """{decl_name: '<binders> : <conclusion>'} for theorem/lemma decls."""
    heads = list(_DECL_NAME_RE.finditer(text))
    out: dict[str, str] = {}
    for i, m in enumerate(heads):
        name = m.group(1)
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        sig = _dd._extract_full_signature(text[m.start():end])
        if sig:
            out[name] = sig
    return out


def _survivor(a_fqn: str, b_fqn: str) -> str:
    """Deterministic: keep the shorter bare name (usually the more general /
    canonical), tie → lexicographically smaller fqn."""
    a, b = a_fqn.rsplit(".", 1)[-1], b_fqn.rsplit(".", 1)[-1]
    if len(a) != len(b):
        return a_fqn if len(a) < len(b) else b_fqn
    return min(a_fqn, b_fqn)


def _ensure_import(text: str, module: str) -> str:
    if f"import {module}" in text:
        return text
    lines = text.split("\n")
    last = max((i for i, l in enumerate(lines) if l.startswith("import ")),
               default=-1)
    lines.insert(last + 1, f"import {module}")
    return "\n".join(lines)


def _update_index(conn, dropped_fqns: "set[str]") -> None:
    """Bookkeep dedup drops in the DB index (v18: was editing INDEX.md
    entry lines): placed rows whose target_name was dropped flip to
    lifecycle='dropped' so no consumer (context menu / dedupe pool /
    pre-search filter) keeps offering the removed decl. conn=None
    (standalone campaign) → loud skip; the operator re-runs library-verify
    which surfaces any resulting drift."""
    if conn is None:
        if dropped_fqns:
            print(f"[dedup] WARNING: {len(dropped_fqns)} drop(s) not "
                  f"recorded in the DB index (no conn — standalone run)",
                  flush=True)
        return
    for fqn in sorted(dropped_fqns):
        conn.execute(
            "UPDATE library_decls SET lifecycle='dropped', updated_at=?"
            " WHERE target_name = ? AND lifecycle IN ('migrated','cleaned')",
            (__import__("Tooling.state.db", fromlist=["now"]).now(), fqn))
    conn.commit()


def _load_decls(workspace: Path, problem: str,
                scope_index: "list[tuple[str, str]] | None" = None,
                conn=None,
                ) -> "tuple[list[_Decl], list[_Decl]]":
    """(scope decls for `problem`, domain pool decls). Both theorem/lemma
    with parseable sigs.

    `scope_index`: optional `[(fqn, rel)]` for the scope. In-chain, cleanup
    runs BEFORE the bridge marker is set, so the problem's own decls aren't
    in the pool index yet — the caller supplies them from the DB (migrated
    rows' target_name/target_file). None → read scope from the DB index
    (standalone). The pool always comes from the DB index (= other,
    already-BRIDGED problems; v18 — was INDEX.md)."""
    domain = problem.split(".")[0] if "." in problem else problem
    index = _db_index(conn)
    sig_cache: dict[str, dict[str, str]] = {}

    def decl(fqn: str, rel: str) -> "_Decl | None":
        if rel not in sig_cache:
            try:
                sig_cache[rel] = _file_full_sigs(
                    (workspace / rel).read_text(encoding="utf-8"))
            except OSError:
                sig_cache[rel] = {}
        name = fqn.rsplit(".", 1)[-1]
        sig = sig_cache[rel].get(name)
        if not sig:
            return None
        cp = _type_colon_pos(sig)
        concl = sig[cp + 1:] if cp >= 0 else sig
        bc = _dd._signature_binder_count("theorem _ " + sig + " := by sorry")
        return _Decl(fqn, rel, _mod_of_fqn(fqn), name, sig, bc,
                     _dd._distinctive_tokens(concl))

    scope_src = scope_index if scope_index is not None else index.get(problem, [])
    scope = [d for d in (decl(f, r) for f, r in scope_src) if d]
    pool: list[_Decl] = []
    for ents in index.values():
        for f, r in ents:
            parts = r.replace("\\", "/").split("/")
            if len(parts) >= 2 and parts[0] == "Library" and parts[1] == domain:
                d = decl(f, r)
                if d:
                    pool.append(d)
    return scope, pool


def _nonscope_library_texts(workspace: Path, scope_rels: "set[str]"
                            ) -> "list[tuple[str, str]]":
    """Read every Library `.lean` OUTSIDE the scope problem ONCE — the corpus
    `_external_consumer` scans. Built once per classify run + reused across all
    drop candidates, so the cross-problem guard is O(library) not O(library ×
    candidates) (§12 scaling fix; the per-candidate rglob+read was classify's
    #1 cost — ~220s on courant)."""
    out: list[tuple[str, str]] = []
    lib = workspace / "Library"
    sset = set(scope_rels)
    for f in lib.rglob("*.lean"):
        rel = f.relative_to(workspace).as_posix()
        if rel in sset:
            continue
        try:
            out.append((rel, f.read_text(encoding="utf-8")))
        except OSError:
            continue
    return out


def _external_consumer(workspace: Path, X: _Decl, scope_rels: "set[str]", *,
                       nonscope: "list[tuple[str, str]] | None" = None
                       ) -> "str | None":
    """Return the rel-path of a Library file OUTSIDE the scope problem that
    references decl X (by fqn, or by bare name while importing X's module),
    or None. Cleanup only rewrites the scope problem's files, so a decl with a
    CROSS-PROBLEM consumer must NOT be dropped here (the scope-only gate would
    not catch the breakage) — deferred to the future cross-problem rewire.
    Cross-problem Library→Library refs are real (NormalDiagonalization→Schur,
    RCF→InvariantFactor). `nonscope` = a pre-read corpus (caller builds it once
    per classify run); falls back to a fresh read for ad-hoc callers."""
    items = (nonscope if nonscope is not None
             else _nonscope_library_texts(workspace, scope_rels))
    for rel, t in items:
        if replace_token(t, X.fqn, X.fqn)[1] > 0:
            return rel
        if f"import {X.module}" in t and replace_token(t, X.name, X.name)[1] > 0:
            return rel
    return None


def _apply_drop(workspace: Path, scope_rels: "list[str]",
                X: _Decl, Y: _Decl) -> bool:
    """Drop X (survivor Y): drop_decl + rewire refs across the problem's
    Library files, then build the problem's modules. Keep on success, else
    restore the snapshot. Returns True iff committed."""
    from ...pipeline._lake import lake_build_modules
    snap = {}
    for rel in scope_rels:
        try:
            snap[rel] = (workspace / rel).read_text(encoding="utf-8")
        except OSError:
            return False
    try:
        new = dict(snap)
        dropped_text, removed = drop_decl(new[X.rel], X.name)
        if not removed:
            return False
        new[X.rel] = dropped_text
        for rel in new:
            t = new[rel]
            t, _ = replace_token(t, X.fqn, Y.fqn)     # FQN refs
            t, _ = replace_token(t, X.name, Y.fqn)    # bare refs → full Y
            if Y.module and _mod_of_rel(rel) != Y.module and Y.fqn in t:
                t = _ensure_import(t, Y.module)   # '' = Mathlib, no import
            new[rel] = t
        for rel, t in new.items():
            (workspace / rel).write_text(t, encoding="utf-8")
        prob_modules = sorted({_mod_of_rel(r) for r in scope_rels})
        ok, _msg = lake_build_modules(workspace, prob_modules)
        if ok:
            return True
    except Exception:  # noqa: BLE001
        pass
    for rel, t in snap.items():       # revert
        (workspace / rel).write_text(t, encoding="utf-8")
    return False


def apply_bridge(workspace: Path, scope_rels: "list[str]",
                 X: _Decl, Y: _Decl, bridge: str) -> bool:
    """Collapse X's proof to `:= <bridge>` (a one-liner citing Y), keeping X's
    statement so consumers are untouched (the v1b-② near-dup move). Option-1
    gate hierarchy (sig-preserving → file-local):

      1. per-decl ISOLATED build (`_build_decl_isolated`) — cheaply reject a bad
         bridge with no file write, no whole-problem rebuild;
      2. replace the proof in X's OWN file (+ import Y's module);
      3. per-FILE build of X's module only — the edit is sig-preserving, so
         consumers are unaffected (no whole-problem rebuild needed).

    Reverts X's file on any failure. (`scope_rels` kept for signature
    compatibility; only X's file is touched.)"""
    from ...pipeline._lake import lake_build_modules
    # (1) inner gate: build the bridged decl in isolation (Library file
    # namespace == its module, so `open X.module` resolves bare sibling refs).
    mods = [X.module] + ([Y.module] if Y.module else [])
    ok, _detail = _build_decl_isolated(
        workspace, sig=X.sig, proof=bridge, modules=mods, namespaces=[X.module],
        opens=_file_opens(workspace, X.rel))
    if not ok:
        return False
    # (2) stage: replace X's proof in its own file.
    try:
        orig = (workspace / X.rel).read_text(encoding="utf-8")
    except OSError:
        return False
    new_t, replaced = replace_proof(orig, X.name, bridge)
    if not replaced:
        return False
    if Y.module and _mod_of_rel(X.rel) != Y.module:
        new_t = _ensure_import(new_t, Y.module)       # '' = Mathlib, no import
    (workspace / X.rel).write_text(new_t, encoding="utf-8")
    # (3) per-file build: only X's module is affected (sig unchanged).
    try:
        ok3, _msg = lake_build_modules(workspace, [_mod_of_rel(X.rel)])
        if ok3:
            return True
    except Exception:  # noqa: BLE001
        pass
    (workspace / X.rel).write_text(orig, encoding="utf-8")    # revert
    return False


def apply_merge(workspace: Path, scope_rels: "list[str]",
                X: _Decl, Y: _Decl) -> bool:
    """Wrapper-merge: when a defeq pair can't be plain-dropped because survivor
    Y is a thin wrapper whose proof cites X (so dropping X would break Y), move
    X's real proof onto Y, then drop X + rewire X refs → Y. Result: Y keeps its
    (better) name and gains the real proof; the wrapper-named X is gone. Build-
    gated; revert on any failure. Returns True iff committed.

    The common harvest pattern: `X_of_finrank` (real proof) + thin `X`
    (`:= by apply X_of_finrank <;> assumption`) — identical statements."""
    from ...pipeline._lake import lake_build_modules
    snap = {}
    for rel in scope_rels:
        try:
            snap[rel] = (workspace / rel).read_text(encoding="utf-8")
        except OSError:
            return False
    try:
        x_body = decl_proof_body(snap[X.rel], X.name)
        if not x_body:
            return False
        new = dict(snap)
        # 1. move X's real proof onto Y (Y no longer cites X). Same file is
        #    fine: new[X.rel] and new[Y.rel] are one entry, edited in sequence.
        ytext, ok = replace_proof(new[Y.rel], Y.name, x_body)
        if not ok:
            return False
        new[Y.rel] = ytext
        # 2. drop X + rewire its refs → Y
        dropped_text, removed = drop_decl(new[X.rel], X.name)
        if not removed:
            return False
        new[X.rel] = dropped_text
        for rel in new:
            t = new[rel]
            t, _ = replace_token(t, X.fqn, Y.fqn)
            t, _ = replace_token(t, X.name, Y.fqn)
            if Y.module and _mod_of_rel(rel) != Y.module and Y.fqn in t:
                t = _ensure_import(t, Y.module)   # '' = Mathlib, no import
            new[rel] = t
        for rel, t in new.items():
            (workspace / rel).write_text(t, encoding="utf-8")
        ok2, _msg = lake_build_modules(
            workspace, sorted({_mod_of_rel(r) for r in scope_rels}))
        if ok2:
            return True
    except Exception:  # noqa: BLE001
        pass
    for rel, t in snap.items():       # revert
        (workspace / rel).write_text(t, encoding="utf-8")
    return False


def run_dedup_campaign(workspace: Path, problem: str, *, apply: bool = False,
                       conn=None) -> "dict[str, str]":
    """Mechanical dedup over `problem`'s Library decls (v1a). Returns
    {dropped_fqn: survivor_fqn}. `apply=False` = dry-run (detect only)."""
    from ...pipeline._lake import lake_build_modules
    scope, pool = _load_decls(workspace, problem, conn=conn)
    print(f"[dedup] {problem}: {len(scope)} scope decls, {len(pool)} domain pool",
          flush=True)
    # ensure oleans built (probe imports them)
    lake_build_modules(workspace, sorted({d.module for d in pool}))
    scope_rels = sorted({d.rel for d in scope})

    dropped: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        alive_scope = [d for d in scope if d.fqn not in dropped]
        alive_pool = [d for d in pool if d.fqn not in dropped]
        pairs: list[tuple[str, str, str]] = []
        origin: list[tuple[_Decl, _Decl]] = []
        for X in alive_scope:
            for Y in alive_pool:
                if Y.fqn == X.fqn or Y.binders != X.binders:
                    continue
                # defeq ⇒ near-identical conclusions. Require high token
                # Jaccard so "shares only common LA tokens (Module/finrank)"
                # pairs are dropped (they caused the cross-problem false hits).
                inter = len(X.concl_tokens & Y.concl_tokens)
                union = len(X.concl_tokens | Y.concl_tokens)
                if union == 0 or inter / union < 0.5:
                    continue
                pairs.append((X.sig, Y.module, Y.fqn))
                origin.append((X, Y))
        if not pairs:
            break
        flags = batch_defeq(workspace, problem, pairs)
        hits: dict[str, list[_Decl]] = {}
        for (X, Y), ok in zip(origin, flags):
            if ok:
                hits.setdefault(X.fqn, []).append(Y)
        for X in alive_scope:
            if X.fqn in dropped:
                continue
            loser_to = next((Y for Y in hits.get(X.fqn, [])
                             if Y.fqn not in dropped
                             and _survivor(X.fqn, Y.fqn) == Y.fqn), None)
            if loser_to is None:
                continue
            ext = _external_consumer(workspace, X, set(scope_rels))
            if ext:
                print(f"[dedup] {X.name}: defeq twin {loser_to.name} but a "
                      f"cross-problem consumer ({ext}) references it → kept "
                      f"(cross-problem rewire = v1b)", flush=True)
                continue
            if not apply:
                dropped[X.fqn] = loser_to.fqn
                changed = True
                continue
            if _apply_drop(workspace, scope_rels, X, loser_to):
                dropped[X.fqn] = loser_to.fqn
                changed = True
                print(f"[dedup] dropped {X.name} → cite {loser_to.name}",
                      flush=True)
                break          # state changed → restart pass
            elif apply_merge(workspace, scope_rels, X, loser_to):
                dropped[X.fqn] = loser_to.fqn
                changed = True
                print(f"[dedup] merged {X.name} → {loser_to.name} "
                      f"(wrapper; moved real proof)", flush=True)
                break
            else:
                print(f"[dedup] {X.name}: defeq-hit but drop+merge build failed "
                      f"→ kept as-is (genuine near; v1b LLM bridger)",
                      flush=True)
        if not apply:
            break   # dry-run: one pass is enough (no state mutation)

    if apply and dropped:
        _update_index(conn, set(dropped))
    return dropped


# ---------------------------------------------------------------------
# v1b — LLM dedup layer (standalone, operator/Agent-orchestrated)
#
# A high-recall LLM marker proposes redundancy; Python proposes nothing
# semantic — it only feeds proposals to the SAME mechanical exact-defeq gate
# (`batch_defeq` → `_apply_drop`, rewire-or-revert) and gates them. The live
# chain uses the per-file AUDIT marker (`_audit_one_file` → `dedup_audit.md` →
# per-decl verdicts). The flat one-shot marker (`mark_context` → `dedup.md` →
# `pairs.json`) was its attention-dispersed precursor and has been retired;
# `find_thin_wrappers` (its mechanical thin-proof detector) is kept for the
# standalone `--thin` scan.
# ---------------------------------------------------------------------

_THIN_MAX_LEN = 120
_AUTOMATION_HEADS = (
    "simp", "simpa", "norm_num", "omega", "aesop", "decide", "rfl", "trivial",
    "assumption", "linarith", "nlinarith", "positivity", "ring", "ring_nf",
    "field_simp", "tauto", "norm_cast", "push_cast", "constructor")


def _cited_lemma(body: str) -> "str | None":
    """The lemma a thin *delegating* proof hands off to — the token after
    `exact`/`apply`/`refine`/`using`, or a term-mode head — or None for a
    pure-automation proof (`by simp` / `norm_num` / …; an inline candidate
    rather than a rename of one lemma)."""
    s = " ".join(body.split())
    m = re.match(r"(?:by\s+)?(?:exact|apply|refine)\s+@?([A-Za-z_][\w'.]*)", s)
    if not m:
        m = re.search(r"\busing\s+@?([A-Za-z_][\w'.]*)", s)
    if not m and not s.startswith("by"):
        m = re.match(r"@?([A-Za-z_][\w'.]*)", s)         # term-mode head
    if not m:
        return None
    name = m.group(1)
    # a bare automation head ("by simp …") is not a delegated lemma
    return None if name in _AUTOMATION_HEADS else name


def find_thin_wrappers(workspace: Path, problem: str, conn=None
                       ) -> "list[tuple[str, str, str | None]]":
    """Flag THIN-proof scope decls — one-liners — as dedup/inline suspicions
    (a thin wrapper's proof literally names its twin). Mechanical detector
    behind the standalone `--thin` scan. Returns
    `[(fqn, oneline_proof, cited_lemma_or_None)]`: `cited` = the lemma a
    delegating one-liner hands off to (its likely twin → a dedup pair), None
    for pure automation (`by simp`/`norm_num` — an inline candidate)."""
    scope, _ = _load_decls(workspace, problem, conn=conn)
    cache: dict[str, str] = {}
    out: list[tuple[str, str, str | None]] = []
    for d in scope:
        if d.rel not in cache:
            try:
                cache[d.rel] = (workspace / d.rel).read_text(encoding="utf-8")
            except OSError:
                cache[d.rel] = ""
        body = decl_proof_body(cache[d.rel], d.name)
        if body is None or body.count("\n") > 1:
            continue
        one = " ".join(body.split())
        if len(one) > _THIN_MAX_LEN:
            continue
        out.append((d.fqn, one, _cited_lemma(body)))
    return out


def _resolve_y(by_fqn: "dict[str, _Decl]", y_fqn: str) -> "tuple[_Decl, bool]":
    """Resolve a marked survivor `y_fqn`. A domain-pool Library decl → that
    _Decl, is_mathlib=False. Otherwise treat it as a Mathlib lemma (the
    mathlib-tier): a synthetic _Decl with module='' (sentinel — Mathlib is
    imported everywhere, so no extra import / no olean to build), is_mathlib=
    True. Unknown/typo names also land here and are harmlessly rejected by the
    isDefEq gate (`@<name>` fails to elaborate)."""
    Y = by_fqn.get(y_fqn)
    if Y is not None:
        return Y, False
    return _Decl(fqn=y_fqn, rel="", module="", name=y_fqn.rsplit(".", 1)[-1],
                 sig="", binders=0, concl_tokens=frozenset()), True


def apply_llm_pairs(workspace: Path, problem: str,
                    pairs: "list[tuple[str, str]]", *, apply: bool = False,
                    scope_index: "list[tuple[str, str]] | None" = None,
                    conn=None) -> "dict":
    """3.0→3.1a: run LLM-marked candidate pairs `(x_fqn dups y_fqn)` through
    the mechanical exact-defeq gate. `x` must be a scope decl; `y` any domain
    decl. A pair lands a DROP only when x≡y (defeq), y is the deterministic
    survivor, and x has no cross-problem consumer — then drop x + rewire
    (rewire-or-revert), identical to v1a. Returns
    `{'dropped': {x:y}, 'near': [(x,y)], 'skipped': [(x,y)]}`; `near` =
    marked but not defeq → the 3.1b bridger's input."""
    scope, pool = _load_decls(workspace, problem, scope_index, conn=conn)
    by_fqn = {d.fqn: d for d in (*pool, *scope)}   # scope wins name clashes
    scope_fqns = {d.fqn for d in scope}
    scope_rels = sorted({d.rel for d in scope})

    # Resolve + validate pairs. batch_defeq builds the canonical oleans it
    # imports (pre-flight) and _apply_drop builds the scope modules, so no
    # top-level pool build is needed; with no valid pair we touch no lake.
    # y not in the domain pool → a Mathlib lemma (the mathlib-tier "kill the
    # wheel"): module='' sentinel, no import, always the survivor.
    probe: list[tuple[str, str, str]] = []
    pair_decls: list[tuple[_Decl, _Decl, bool]] = []
    skipped: list[tuple[str, str]] = []
    for x_fqn, y_fqn in pairs:
        X = by_fqn.get(x_fqn)
        if X is None or x_fqn not in scope_fqns or x_fqn == y_fqn:
            skipped.append((x_fqn, y_fqn))
            continue
        Y, is_mathlib = _resolve_y(by_fqn, y_fqn)
        probe.append((X.sig, Y.module, Y.fqn))
        pair_decls.append((X, Y, is_mathlib))
    flags = batch_defeq(workspace, problem, probe) if probe else []

    dropped: dict[str, str] = {}
    merged: set[str] = set()
    near: list[tuple[str, str]] = []
    for (X, Y, is_mathlib), ok in zip(pair_decls, flags):
        if not ok:
            near.append((X.fqn, Y.fqn))
            continue
        if X.fqn in dropped:
            continue
        if not is_mathlib and _survivor(X.fqn, Y.fqn) != Y.fqn:
            skipped.append((X.fqn, Y.fqn))      # x is the better survivor
            continue                            # (mathlib always wins)
        if _external_consumer(workspace, X, set(scope_rels)):
            skipped.append((X.fqn, Y.fqn))      # cross-problem consumer → v1b-c
            continue
        if not apply:
            dropped[X.fqn] = Y.fqn
            continue
        if _apply_drop(workspace, scope_rels, X, Y):
            dropped[X.fqn] = Y.fqn
            print(f"[dedup-llm] dropped {X.name} → cite "
                  f"{'mathlib ' if is_mathlib else ''}{Y.name}", flush=True)
        elif not is_mathlib and apply_merge(workspace, scope_rels, X, Y):
            dropped[X.fqn] = Y.fqn               # wrapper-merge (moved proof)
            merged.add(X.fqn)
            print(f"[dedup-llm] merged {X.name} → {Y.name} (moved real proof)",
                  flush=True)
        else:
            near.append((X.fqn, Y.fqn))         # genuine near → LLM bridger
    if apply and dropped:
        _update_index(conn, set(dropped))
    return {"dropped": dropped, "merged": merged, "near": near,
            "skipped": skipped}


def bridge_context(workspace: Path, problem: str,
                   near_pairs: "list[tuple[str, str]]",
                   scope_index: "list[tuple[str, str]] | None" = None,
                   conn=None) -> str:
    """Context for the 3.1b bridger: for each near-dup pair, X's full source
    block (statement + the proof to collapse) and Y's signature/fqn to cite."""
    scope, pool = _load_decls(workspace, problem, scope_index, conn=conn)
    by_fqn = {d.fqn: d for d in (*pool, *scope)}
    cache: dict[str, str] = {}

    def block(d: _Decl) -> str:
        if d.rel not in cache:
            try:
                cache[d.rel] = (workspace / d.rel).read_text(encoding="utf-8")
            except OSError:
                cache[d.rel] = ""
        span = decl_span(cache[d.rel], d.name)
        return cache[d.rel][span[0]:span[1]].strip() if span else ""

    lines = [f"# dedup bridge — {problem}",
             "# Each pair: X is defeq-ish to Y but not drop-in substitutable, so",
             "# X stays. Collapse X's PROOF to a one-liner citing Y (keep X's",
             "# statement). Give the bridge as a tactic/term for `:= <bridge>`.", ""]
    for i, (x, y) in enumerate(near_pairs):
        X = by_fqn.get(x)
        if X is None:
            continue
        Y, is_mathlib = _resolve_y(by_fqn, y)
        ysig = "(Mathlib lemma — confirm its statement with loogle)" \
            if is_mathlib else " ".join(Y.sig.split())
        lines += [f"## pair {i}", f"### x = {X.fqn}  (replace its proof)",
                  "```lean", block(X), "```",
                  f"### y = {Y.fqn}  (cite this)",
                  f"{Y.fqn} :: {ysig}", ""]
    return "\n".join(lines)


def run_llm_bridge(workspace: Path, problem: str,
                   near_pairs: "list[tuple[str, str]]", *, apply: bool = False,
                   scope_index: "list[tuple[str, str]] | None" = None,
                   conn=None) -> "dict":
    """v1b-②: spawn the bridger (Context = `bridge_context`, prompt =
    librarian/dedup_bridge.md, JSON out = bridges.json), then collapse each
    proposed near-dup's proof via `apply_bridge` (build-gated; revert on fail).
    Returns `{'bridged': {x:y}, 'failed': [(x,y)], 'rc', 'error'}`."""
    import json
    from ... import agent
    scope, pool = _load_decls(workspace, problem, scope_index, conn=conn)
    by_fqn = {d.fqn: d for d in (*pool, *scope)}
    scope_rels = sorted({d.rel for d in scope})
    fail = {"bridged": {}, "failed": list(near_pairs)}
    pid = agent.new_pipeline_id()
    attempts = agent.attempts_dir_for(workspace, pid)
    (attempts / "Context.md").write_text(
        bridge_context(workspace, problem, near_pairs, scope_index,
                       conn=conn),
        encoding="utf-8")
    prompt_path = workspace / "Tooling" / "prompts" / "librarian" / "dedup_bridge.md"
    problem_dir = workspace.joinpath("Problems", *problem.split("."))
    rc = agent.spawn_llm(
        kind="librarian", prompt_path=prompt_path, problem_dir=problem_dir,
        attempts_dir=attempts, session_id=agent.new_pipeline_id())
    if rc != 0:
        return {**fail, "rc": rc, "error": f"bridger agent rc={rc}"}
    out = attempts / "bridges.json"
    if not out.exists():
        return {**fail, "rc": rc, "error": "bridger wrote no bridges.json"}
    try:
        data = json.loads(_strip_json_fence(out.read_text(encoding="utf-8")))
    except Exception as e:  # noqa: BLE001
        return {**fail, "rc": rc, "error": f"bridges.json invalid: {e}"}
    if not isinstance(data, list):
        return {**fail, "rc": rc, "error": "bridges.json must be a JSON array"}
    bridged: dict[str, str] = {}
    failed: list[tuple[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        x, y, br = item.get("x"), item.get("y"), item.get("bridge")
        X = by_fqn.get(x)
        if X is None or not isinstance(br, str) or not br.strip():
            continue
        Y, _is_mathlib = _resolve_y(by_fqn, y)   # y may be a Mathlib lemma
        if not apply:
            bridged[x] = y
            continue
        if apply_bridge(workspace, scope_rels, X, Y, br.strip()):
            bridged[x] = y
            print(f"[dedup-bridge] collapsed {X.name} → cite {Y.name}",
                  flush=True)
        else:
            failed.append((x, y))
    return {"bridged": bridged, "failed": failed, "rc": rc, "error": ""}


# ---------------------------------------------------------------------
# per-file audit marker (the live chain marker)
#
# One agent per Library file emits a verdict per decl (high recall) at the FILE
# grain — focused, sees within-file siblings, matches the librarian's per-file
# unit — and the mechanical gate absorbs the variance (verdicts → the defeq
# gate; the LLM proposes, lake decides). This is the per-decl AUDIT from the
# old v0.2 design, but gated; it superseded the flat statement-only marker.
# ---------------------------------------------------------------------

_AUDIT_VERDICTS = ("keep", "drop", "cite-mathlib", "cite-library", "merge")


def parse_verdicts(text: str) -> "tuple[list[dict] | None, str]":
    """Parse an audit's verdicts.json → `[{slug, verdict, name}]` (`name` = the
    cited Mathlib/Library lemma or canonical sibling; '' for keep)."""
    import json
    try:
        data = json.loads(_strip_json_fence(text))
    except Exception as e:  # noqa: BLE001
        return None, f"verdicts.json is not valid JSON: {e}"
    if not isinstance(data, list):
        return None, "verdicts.json must be a JSON array"
    out: list[dict] = []
    for i, it in enumerate(data):
        if not isinstance(it, dict) or "slug" not in it or "verdict" not in it:
            return None, f"verdict {i} missing 'slug'/'verdict'"
        v = it["verdict"]
        if v not in _AUDIT_VERDICTS:
            return None, f"verdict {i} unknown verdict {v!r}"
        name = (it.get("name") or it.get("mathlib_name") or it.get("library_name")
                or it.get("canonical") or "")
        out.append({"slug": it["slug"], "verdict": v, "name": str(name)})
    return out, ""


def _audit_pairs(verdicts: "list[dict]", scope_by_leaf: "dict[str, _Decl]",
                 all_by_leaf: "dict[str, _Decl]") -> "list[tuple[str, str]]":
    """Non-keep verdicts → (x_fqn, y) gate pairs. A bare canonical/library slug
    is resolved to its fqn; dotted (Mathlib/Library) names pass through."""
    pairs: list[tuple[str, str]] = []
    for vd in verdicts:
        if vd["verdict"] == "keep" or not vd["name"]:
            continue
        X = scope_by_leaf.get(vd["slug"])
        if X is None:
            continue
        y = vd["name"]
        if "." not in y:
            yd = all_by_leaf.get(y)
            if yd:
                y = yd.fqn
        if y != X.fqn:
            pairs.append((X.fqn, y))
    return pairs


def _file_audit_context(workspace: Path, problem: str, rel: str,
                        scope: "list[_Decl]", pool: "list[_Decl]",
                        *, shortlist: int = 30) -> str:
    """Focused context for ONE file's audit: each decl's statement + proof (so
    thin wrappers are visible), same-problem siblings (for `merge`), and a
    token-nearest Library-pool shortlist (for `cite-library`). Mathlib is via
    loogle, not dumped."""
    try:
        text = (workspace / rel).read_text(encoding="utf-8")
    except OSError:
        text = ""
    file_decls = [d for d in scope if d.rel == rel]
    ftokens: "frozenset[str]" = frozenset().union(
        *(d.concl_tokens for d in file_decls)) if file_decls else frozenset()
    lines = [f"# dedup audit — {problem}", f"# file: {rel}",
             f"# Give a verdict for EACH of these {len(file_decls)} decls.", ""]
    for d in file_decls:
        proof = " ".join((decl_proof_body(text, d.name) or "").split())
        if len(proof) > 240:
            proof = proof[:240] + " …"
        lines += [f"## {d.fqn}",
                  f"  statement :: {' '.join(d.sig.split())}",
                  f"  proof     :: {proof}", ""]
    sibs = [d for d in scope if d.rel != rel]
    if sibs:
        lines.append(f"# same-problem siblings ({len(sibs)}) — targets for `merge`:")
        lines += [f"{d.fqn} :: {' '.join(d.sig.split())}"
                  for d in sorted(sibs, key=lambda d: d.fqn)]
    ranked = sorted((d for d in pool if d.concl_tokens & ftokens),
                    key=lambda d: len(d.concl_tokens & ftokens), reverse=True)
    near_pool = ranked[:shortlist]
    if near_pool:
        lines.append(f"# nearest Library pool ({len(near_pool)}) — targets for `cite-library`:")
        lines += [f"{d.fqn} :: {' '.join(d.sig.split())}" for d in near_pool]
    return "\n".join(lines)


def _audit_one_file(workspace: Path, problem: str, rel: str,
                    scope: "list[_Decl]", pool: "list[_Decl]",
                    scope_by_leaf: "dict[str, _Decl]",
                    all_by_leaf: "dict[str, _Decl]", prompt_path: Path,
                    problem_dir: Path) -> "tuple[list[tuple[str, str]], str]":
    """Audit ONE file: spawn an agent over its focused context, parse verdicts,
    return (non-keep pairs, log line). Pure marking — no Library mutation — so
    files run concurrently (each in its own attempts dir)."""
    from ... import agent
    leaf = rel.split("/")[-1]
    attempts = agent.attempts_dir_for(workspace, agent.new_pipeline_id())
    (attempts / "Context.md").write_text(
        _file_audit_context(workspace, problem, rel, scope, pool),
        encoding="utf-8")
    rc = agent.spawn_llm(kind="librarian", prompt_path=prompt_path,
                         problem_dir=problem_dir, attempts_dir=attempts,
                         session_id=agent.new_pipeline_id())
    out = attempts / "verdicts.json"
    if rc != 0 or not out.exists():
        return [], f"[dedup-audit] {leaf}: rc={rc}, no verdicts"
    vds, err = parse_verdicts(out.read_text(encoding="utf-8"))
    if err:
        return [], f"[dedup-audit] {leaf}: {err}"
    fp = _audit_pairs(vds, scope_by_leaf, all_by_leaf)
    return fp, f"[dedup-audit] {leaf}: {len(vds)} verdicts, {len(fp)} non-keep"


def _file_topo_order(workspace: Path, scope: "list[_Decl]") -> "list[str]":
    """Bottom-up topo order (deps first) of the problem's scope file rels, read
    from their `import` lines: file R depends on scope file S iff R imports S's
    module. A file lands after every in-scope dep, so a rebuild publishes fresh
    dependency oleans before importers (and §13's per-file cleanup cleans the
    foundation before its consumers). Cycle → leftovers appended (stable).

    Mirrors `pipeline.librarian._topo_files` (the framework twin 3c-2 will use
    via the dispatcher); inlined to keep this engine standalone / DB-free."""
    mod2rel = {d.module: d.rel for d in scope if d.module}
    files = sorted({d.rel for d in scope})
    deps: dict[str, set[str]] = {r: set() for r in files}
    imp_re = re.compile(r"^\s*import\s+([\w.]+)", re.M)
    for r in files:
        try:
            text = (workspace / r).read_text(encoding="utf-8")
        except OSError:
            continue
        for m in imp_re.findall(text):
            d = mod2rel.get(m)
            if d and d != r:
                deps[r].add(d)
    indeg = {r: len(deps[r]) for r in files}
    users: dict[str, list[str]] = {r: [] for r in files}
    for r in files:
        for d in deps[r]:
            users[d].append(r)
    ready = sorted(r for r in files if indeg[r] == 0)
    out: list[str] = []
    while ready:
        f = ready.pop(0)
        out.append(f)
        for u in users[f]:
            indeg[u] -= 1
            if indeg[u] == 0:
                ready = sorted(ready + [u])
    out += [r for r in files if r not in out]      # cycle fallback
    return out


def _file_dep_closure(workspace: Path, scope: "list[_Decl]"
                      ) -> "dict[str, frozenset[str]]":
    """{rel: every scope file rel it TRANSITIVELY imports}. A cross-file drop
    X→Y is only safe when Y's file is in X's file's closure (or same file): then
    every consumer of X (each imports X's file) sees Y transitively, with no
    import cycle. A survivor in a topo-LATER (consumer) file inverts the deps and
    breaks the rewire — the `GridConstruction.monotone_grid → GridReindex.sorted_grid`
    bug, where the chosen (shorter-named) survivor lived in X's consumer."""
    mod2rel = {d.module: d.rel for d in scope if d.module}
    files = sorted({d.rel for d in scope})
    direct: dict[str, set[str]] = {r: set() for r in files}
    imp_re = re.compile(r"^\s*import\s+([\w.]+)", re.M)
    for r in files:
        try:
            text = (workspace / r).read_text(encoding="utf-8")
        except OSError:
            continue
        for m in imp_re.findall(text):
            d = mod2rel.get(m)
            if d and d != r:
                direct[r].add(d)

    def reach(r: str) -> set[str]:
        seen: set[str] = set()
        stack = list(direct.get(r, ()))
        while stack:
            d = stack.pop()
            if d in seen:
                continue
            seen.add(d)
            stack.extend(direct.get(d, ()))
        return seen

    return {r: frozenset(reach(r)) for r in files}


def _collect_marked_pairs(workspace: Path, problem: str, *, concurrency: int = 4,
                          scope_index: "list[tuple[str, str]] | None" = None,
                          conn=None) -> "tuple[list[tuple[str, str]], list[_Decl], list[_Decl]]":
    """Per-file audit marking (parallel): one agent per Library file emits a
    verdict per decl → uniq (x_fqn, y_fqn) pairs. The shared precursor of both
    the legacy batch gate (`run_file_audit_dedup`) and the staged pipeline
    (`run_staged_cleanup`). Returns (uniq_pairs, scope, pool)."""
    from concurrent.futures import ThreadPoolExecutor
    scope, pool = _load_decls(workspace, problem, scope_index, conn=conn)
    scope_by_leaf = {d.name: d for d in scope}
    all_by_leaf = {d.name: d for d in (*pool, *scope)}
    files = sorted({d.rel for d in scope})
    print(f"[dedup-audit] {problem}: {len(files)} files, {len(scope)} decls "
          f"(marking ×{max(1, concurrency)} parallel)", flush=True)
    prompt_path = workspace / "Tooling" / "prompts" / "librarian" / "dedup_audit.md"
    problem_dir = workspace.joinpath("Problems", *problem.split("."))
    all_pairs: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futs = [ex.submit(_audit_one_file, workspace, problem, rel, scope, pool,
                          scope_by_leaf, all_by_leaf, prompt_path, problem_dir)
                for rel in files]
        for fut in futs:                       # submission order = stable logs
            fp, log = fut.result()
            print(log, flush=True)
            all_pairs.extend(fp)
    return sorted({p for p in all_pairs}), scope, pool


def _resolve_drop_chains(plan: "dict[str, tuple[_Decl, str]]",
                         by_fqn: "dict[str, _Decl]"
                         ) -> "dict[str, tuple[_Decl, str]]":
    """Repoint each drop's survivor to the FINAL non-dropped survivor, so no
    drop cites a decl that is itself dropped this round (X→Y→Z ⇒ X→Z). The
    stale-olean isolate gate cannot catch an intermediate-survivor breakage, so
    we resolve chains up front (§13 soundness). Mutates + returns `plan`."""
    drop_fqns = {x for x, (_Y, k) in plan.items() if k == "drop"}

    def _final(fqn: str, depth: int = 0) -> str:
        ent = plan.get(fqn)
        if ent and ent[1] == "drop" and fqn in drop_fqns and depth < 64:
            return _final(ent[0].fqn, depth + 1)
        return fqn
    for x, (Y, k) in list(plan.items()):
        if k == "drop":
            fz = _final(Y.fqn)
            if fz != Y.fqn and fz in by_fqn:
                plan[x] = (by_fqn[fz], "drop")
    return plan


def _classify_pairs(workspace: Path, problem: str,
                    pairs: "list[tuple[str, str]]", *,
                    scope_index: "list[tuple[str, str]] | None" = None,
                    prior_dropped: "set[str]" = frozenset(),
                    prior_survivors: "set[str]" = frozenset(),
                    conn=None) -> "tuple[dict[str, tuple[_Decl, str]], list[tuple[str, str]]]":
    """Plan the staged gate WITHOUT applying (§13). Classify each marked
    (x_fqn, y_fqn) into drop / bridge / skip — mirrors `apply_llm_pairs`'s
    mechanical gate: exact-defeq + Y-is-survivor + no cross-problem consumer →
    drop; not-defeq → bridge; else skip. Drop wins over bridge for the same x.
    Within-run drop targets are chain-resolved to a final non-dropped survivor
    (X→Y→Z ⇒ X→Z; the stale-olean isolate gate would miss an intermediate-
    survivor breakage, §13 soundness). Returns (plan{x_fqn:(Y,'drop'|'bridge')},
    skipped).

    Per-file (3c-2) cross-file chain guard: `prior_survivors` = decls already
    cited as a drop survivor by an EARLIER (cleaned) file — must NOT be dropped
    (those files are done citing them); `prior_dropped` = decls already dropped
    by an earlier file — never a valid new survivor (stale target). Both → skip
    (conservative; the rare cross-file chain becomes a leftover, not a misfire)."""
    scope, pool = _load_decls(workspace, problem, scope_index, conn=conn)
    by_fqn = {d.fqn: d for d in (*pool, *scope)}
    scope_fqns = {d.fqn for d in scope}
    scope_rels = {d.rel for d in scope}
    dep_closure = _file_dep_closure(workspace, scope)   # X.rel → its imports
    probe: list[tuple[str, str, str]] = []
    decls: list[tuple[_Decl, _Decl, bool]] = []
    skipped: list[tuple[str, str]] = []
    for x_fqn, y_fqn in pairs:
        X = by_fqn.get(x_fqn)
        if X is None or x_fqn not in scope_fqns or x_fqn == y_fqn:
            skipped.append((x_fqn, y_fqn))
            continue
        Y, is_mathlib = _resolve_y(by_fqn, y_fqn)
        probe.append((X.sig, Y.module, Y.fqn))
        decls.append((X, Y, is_mathlib))
    flags = batch_defeq(workspace, problem, probe) if probe else []
    nonscope = None        # cross-problem corpus, read once on first drop candidate
    plan: dict[str, tuple[_Decl, str]] = {}
    for (X, Y, is_mathlib), ok in zip(decls, flags):
        if not ok:
            plan.setdefault(X.fqn, (Y, "bridge"))      # drop (below) overrides
            continue
        if plan.get(X.fqn, (None, ""))[1] == "drop":
            continue
        # `_survivor` (shorter name) may disagree with the marker's chosen
        # survivor Y. batch_defeq only verified `@Y proves X` (the drop-X
        # direction), so we can never safely REVERSE to drop Y. Cross-file: defer
        # to the deterministic survivor so two parallel per-file workers that both
        # mark the pair (X→Y and Y→X) pick the same loser (race-safe). Same-file:
        # one worker owns both decls (no race) → trust the marker and drop X→Y;
        # skipping the same-file case merely because the dup had the shorter name
        # was a recall bug (Finding A — `termwise_eigenvalue_bound` et al.).
        #
        # Cross-file ALSO requires the survivor Y to live in X's dependency
        # closure: dropping X rewires its consumers to Y, which only type-checks
        # if every consumer of X (each imports X's file) can see Y. If Y sits in a
        # topo-LATER (consumer) file the rewire inverts deps → unbuildable Library
        # (the GridConstruction→GridReindex bug; per-file #check missed it because
        # it builds against the dependency's STALE pre-drop olean).
        if not is_mathlib and X.rel != Y.rel and (
                _survivor(X.fqn, Y.fqn) != Y.fqn
                or Y.rel not in dep_closure.get(X.rel, frozenset())):
            skipped.append((X.fqn, Y.fqn))             # cross-file: not safely rewirable
            continue
        if X.fqn in prior_survivors or Y.fqn in prior_dropped:
            skipped.append((X.fqn, Y.fqn))             # per-file cross-file chain
            continue
        if nonscope is None:
            nonscope = _nonscope_library_texts(workspace, scope_rels)
        if _external_consumer(workspace, X, scope_rels, nonscope=nonscope):
            skipped.append((X.fqn, Y.fqn))             # cross-problem consumer
            continue
        plan[X.fqn] = (Y, "drop")
    return _resolve_drop_chains(plan, by_fqn), skipped


def _propose_bridges(workspace: Path, problem: str,
                     pairs: "list[tuple[str, str]]", *,
                     scope_index: "list[tuple[str, str]] | None" = None,
                     conn=None) -> "dict[str, str]":
    """Spawn the bridger for `pairs` (the 'bridge'-classified near-dups) and
    return {x_fqn: bridge_str} — proposed one-line proofs, NOT applied (the
    staged loop applies them per-decl via isolate-build + splice). Batch spawn;
    empty dict on any failure."""
    import json
    from ... import agent
    if not pairs:
        return {}
    pid = agent.new_pipeline_id()
    attempts = agent.attempts_dir_for(workspace, pid)
    (attempts / "Context.md").write_text(
        bridge_context(workspace, problem, pairs, scope_index,
                       conn=conn), encoding="utf-8")
    prompt_path = workspace / "Tooling" / "prompts" / "librarian" / "dedup_bridge.md"
    problem_dir = workspace.joinpath("Problems", *problem.split("."))
    rc = agent.spawn_llm(
        kind="librarian", prompt_path=prompt_path, problem_dir=problem_dir,
        attempts_dir=attempts, session_id=agent.new_pipeline_id())
    out = attempts / "bridges.json"
    if rc != 0 or not out.exists():
        return {}
    try:
        data = json.loads(_strip_json_fence(out.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        return {}
    bridges: dict[str, str] = {}
    if isinstance(data, list):
        for it in data:
            if (isinstance(it, dict) and it.get("x")
                    and isinstance(it.get("bridge"), str) and it["bridge"].strip()):
                bridges[it["x"]] = it["bridge"].strip()
    return bridges


class _Splicer:
    """Serializes the only shared write in staged cleanup — the mechanical
    splice of an isolate-verified edit into a real file. 3c-1: plain write
    (serial). 3c-2: per-target-file lock (in-process → cross-process)."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def write(self, rel: str, text: str) -> None:
        (self.workspace / rel).write_text(text, encoding="utf-8")


def _cleanup_one_file(workspace: Path, rel: str, decls: "list[_Decl]",
                      plan: "dict[str, tuple[_Decl, str]]",
                      bridges: "dict[str, str]",
                      rename_map: "list[tuple[_Decl, _Decl]]",
                      splicer: "_Splicer") -> "dict":
    """§13 deferred-rewire — clean ONE file, writing ONLY this file. First apply
    INCOMING renames (deps that dropped decls this file uses), then this file's
    own marked decls (local drop, same-file wrapper-merge, bridge), then write.

    NO per-file build (§13 (e) skipped for dedup): exact-defeq drops + renames
    are type-safe by construction (classify proved `X ≡ Y`, so any consumer
    typechecks with Y), and bridges are per-decl isolate-verified
    (`_build_decl_isolated`); the chain's bridge Gate B is the integration
    backstop that catches any mechanical-rewrite bug. Drops are RETURNED (not
    pushed into consumer files) — consumers self-apply on their own turn. (e)'s
    `_build_file_copy_isolated` is reserved for future P2 polish, whose edits are
    NOT defeq-safe. Returns `{drops:{x_fqn:Y_decl}, merged:[x_fqn],
    bridged:[(x_fqn,Y_decl)], near:[(x,y)], failed:[(x,y)]}`."""
    out = {"drops": {}, "merged": [], "bridged": [], "near": [], "failed": []}
    try:
        base = (workspace / rel).read_text(encoding="utf-8")
    except OSError:
        out["near"] = [(d.fqn, plan[d.fqn][0].fqn) for d in decls if d.fqn in plan]
        return out

    def _rewire(text: str, xfqn: str, xname: str, Y: _Decl) -> str:
        # Qualified refs (`Mod.xname`) always → Y.fqn. BARE refs: a SAME-MODULE
        # rewrite (a P4 rename, or a same-module wrapper-merge) keeps them bare
        # (Y.name) — the consumer's existing `open`/import of that module resolves
        # the new name, it stays idiomatic, AND it stays matchable by downstream
        # bare-name passes (cite-drop's `_inline_wrapper_call` ignores an FQN
        # tail, so an over-qualified rename ref would dangle when its alias is
        # later dropped). A CROSS-MODULE drop must fully-qualify (the consumer may
        # not open the survivor's namespace).
        t, n1 = replace_token(text, xfqn, Y.fqn)
        bare = Y.name if (Y.module and _mod_of_fqn(xfqn) == Y.module) else Y.fqn
        t, n2 = replace_token(t, xname, bare)
        if (n1 or n2) and Y.module and _mod_of_rel(rel) != Y.module:
            t = _ensure_import(t, Y.module)
        return t

    text = base                                    # mandatory: incoming renames
    for X, Y in rename_map:
        text = _rewire(text, X.fqn, X.name, Y)

    drops: dict[str, _Decl] = {}
    merged: list[str] = []
    bridged: list[tuple[str, _Decl]] = []
    near: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []
    for d in decls:                                # this file's own marked decls
        ent = plan.get(d.fqn)
        if ent is None:
            continue
        Y, kind = ent
        if kind == "drop":
            if Y.rel == rel:                       # same-file wrapper survivor →
                ybody = decl_proof_body(text, Y.name) or ""   # move d's proof up
                if d.name in ybody or d.fqn in ybody:
                    xbody = decl_proof_body(text, d.name)
                    if xbody:
                        yt, okm = replace_proof(text, Y.name, xbody)
                        if okm:
                            text = yt
                            merged.append(d.fqn)
            dropped_text, removed = drop_decl(text, d.name)
            if not removed:
                near.append((d.fqn, Y.fqn))
                continue
            text = _rewire(dropped_text, d.fqn, d.name, Y)
            drops[d.fqn] = Y
        else:                                      # bridge (sig-preserving)
            br = bridges.get(d.fqn)
            # Reject a cross-file bridge that would close an import cycle: citing
            # Y adds `import Y.module` to this file, but Y.module already
            # (transitively) imports this file's module — so the module stops
            # building. The per-decl gate below can't see it (#41).
            x_mod = _mod_of_rel(rel)
            if (br and Y.module and Y.module != x_mod
                    and _imports_reaches(workspace, Y.module, x_mod)):
                failed.append((d.fqn, Y.fqn))
                continue
            iso = bool(br) and d.fqn != Y.fqn and Y.fqn not in drops and \
                _build_decl_isolated(
                    workspace, sig=d.sig, proof=br, namespaces=[d.module],
                    modules=[d.module] + ([Y.module] if Y.module else []),
                    opens=_opens_in(text))[0]
            if not iso:
                failed.append((d.fqn, Y.fqn))
                continue
            nt, replaced = replace_proof(text, d.name, br)
            if not replaced:
                failed.append((d.fqn, Y.fqn))
                continue
            if Y.module and _mod_of_rel(rel) != Y.module:
                nt = _ensure_import(nt, Y.module)
            text = nt
            bridged.append((d.fqn, Y))

    if text != base:
        splicer.write(rel, text)
    out.update(drops=drops, merged=merged, bridged=bridged,
               near=near, failed=failed)
    return out


def run_staged_cleanup(workspace: Path, problem: str, *, apply: bool = False,
                       bridge: bool = True, concurrency: int = 4,
                       scope_index: "list[tuple[str, str]] | None" = None,
                       conn=None) -> "dict":
    """§13 staged cleanup (3c-1, SERIAL): mark (per-file batch parallel) →
    classify (drop/bridge/skip, chain-resolved) → for each file in TOPO order,
    each decl in source order, apply via isolate-then-splice — drop = mechanical
    drop+rewire with each touched file isolate-typechecked before any write;
    bridge = collapse proof, per-decl isolate build. decl-cleanup / file-cleanup
    stages are no-op (dedup only). No per-edit whole-problem rebuild: the
    isolate gates are the fast pre-checks and the chain's bridge Gate B (or a
    manual build for the standalone CLI) is the integration backstop. Returns
    the run_file_audit_dedup shape. 3c-2 lifts this to a per-file dispatcher
    work-kind + parallel via a locking `_Splicer`."""
    import time as _t
    _c = _t.perf_counter
    _t0 = _c()
    uniq, scope, _pool = _collect_marked_pairs(
        workspace, problem, concurrency=concurrency, scope_index=scope_index,
        conn=conn)
    _t1 = _c()
    plan, skipped = _classify_pairs(workspace, problem, uniq,
                                    scope_index=scope_index, conn=conn)
    _t2 = _c()
    bridge_pairs = [(x, Y.fqn) for x, (Y, k) in plan.items() if k == "bridge"]
    bridges = (_propose_bridges(workspace, problem, bridge_pairs, conn=conn,
                                scope_index=scope_index)
               if (apply and bridge) else {})
    _t3 = _c()
    print(f"[staged-timing] mark={_t1 - _t0:.0f}s classify={_t2 - _t1:.0f}s "
          f"bridge-propose={_t3 - _t2:.0f}s "
          f"({len(bridge_pairs)} bridge-pairs)", flush=True)
    order = _file_topo_order(workspace, scope)
    by_fqn = {d.fqn: d for d in scope}
    by_rel: dict[str, list[_Decl]] = {}
    for d in scope:                                # _load_decls keeps source order
        by_rel.setdefault(d.rel, []).append(d)
    splicer = _Splicer(workspace)
    dropped: dict[str, str] = {}
    merged: set[str] = set()
    bridged: dict[str, str] = {}
    near: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []
    if not apply:                                  # dry: classification counts
        for x, (Y, kind) in plan.items():
            if kind == "drop":
                dropped[x] = Y.fqn
            else:
                near.append((x, Y.fqn))
        return {"dropped": dropped, "bridged": bridged, "near": near,
                "skipped": skipped, "bridge_failed": failed, "merged": merged,
                "proposed": len(uniq)}
    rename_map: list[tuple[_Decl, _Decl]] = []     # accumulated drops (X, Y)
    for rel in order:                              # files: deps first (deferred)
        r = _cleanup_one_file(workspace, rel, by_rel.get(rel, []), plan,
                              bridges, rename_map, splicer)
        for xf, Yd in r["drops"].items():
            dropped[xf] = Yd.fqn
            rename_map.append((by_fqn[xf], Yd))    # propagate to later consumers
            tag = "merged" if xf in r["merged"] else "dropped"
            print(f"[staged] {tag} {xf.rsplit('.', 1)[-1]} → cite {Yd.name}",
                  flush=True)
        merged.update(r["merged"])
        for xf, Yd in r["bridged"]:
            bridged[xf] = Yd.fqn
            print(f"[staged] bridged {xf.rsplit('.', 1)[-1]} → cite {Yd.name}",
                  flush=True)
        near.extend(r["near"])
        failed.extend(r["failed"])
    print(f"[staged-timing] apply(per-file drop/merge/bridge-isolate)="
          f"{_c() - _t3:.0f}s  total={_c() - _t0:.0f}s", flush=True)
    if dropped:
        _update_index(conn, set(dropped))     # bridged keep their statement
    return {"dropped": dropped, "bridged": bridged, "near": near,
            "skipped": skipped, "bridge_failed": failed, "merged": merged,
            "proposed": len(uniq)}


def _decl_from_fqn(fqn: str, by_fqn: "dict[str, _Decl]") -> _Decl:
    """Minimal `_Decl` for a rename endpoint known only by FQN (a DB-recorded
    drop / survivor in the per-file path). Prefer the loaded decl (correct
    module); else reconstruct — module='' when the FQN is not a known Library
    decl (= a Mathlib survivor, needs no import)."""
    d = by_fqn.get(fqn)
    if d is not None:
        return d
    return _Decl(fqn=fqn, rel="", module="", name=fqn.rsplit(".", 1)[-1],
                 sig="", binders=0, concl_tokens=frozenset())


# ---------------------------------------------------------------------
# P3-(2) — variable extraction (§13 (e) file-cleanup, whole-file)
#
# migrate emits decls in a raw style: every binder is crammed into a leading
# `∀ …,` in the statement and re-`intro`d at the top of the proof, and binders
# shared across the file are repeated on every decl. This pass rewrites the file
# into idiomatic form — un-∀ the prefix into the binder list, hoist file-wide
# shared binders into one `variable` block — WITHOUT changing any decl's
# elaborated type, so no caller breaks.
#
# Safety (the user-chosen gate): not code-token (the code legitimately changes)
# and not a consumer cone build. Instead `#check @<decl>` each decl's fully-
# applied type before and after (one isolate build, also the proof gate, via
# `lean --json`); any type that differs → session-retry → revert. This enforces
# call-site-invariance by building ONLY this file — Lean resolves `variable`
# inclusion (which a textual parser can't: e.g. `Submodule K V` silently pulls
# in `[Module K V]`), we just compare its answer. A mechanical pre-filter skips
# files with nothing to un-∀ and no shared binders.
# ---------------------------------------------------------------------


def _bracket_groups(region: str) -> "list[str]":
    """Top-level `{..}` / `[..]` / `(..)` binder atoms in `region`, normalized.
    Bracket-balanced (counts only the opening kind, so inner `[K]` in
    `(f : V →ₗ[K] V)` doesn't end the group)."""
    out: list[str] = []
    i, n = 0, len(region)
    closing = {"(": ")", "{": "}", "[": "]"}
    while i < n:
        c = region[i]
        if c in closing:
            close, depth, j = closing[c], 1, i + 1
            while j < n and depth > 0:
                if region[j] == c:
                    depth += 1
                elif region[j] == close:
                    depth -= 1
                j += 1
            out.append(" ".join(region[i:j].split()))
            i = j
        else:
            i += 1
    return out


def _binder_atoms(sig: str) -> "list[str]":
    """Leading binder atoms a caller of this decl supplies, in order — the
    explicit binders before the type colon plus, for a ∀-prenex statement, the
    binders under the leading `∀ …,`. Approximate (a hint + skip heuristic for
    the variable pass); the #check gate is the real check."""
    cp = _type_colon_pos(sig)
    region = sig[:cp].strip() if cp >= 0 else ""
    concl = (sig[cp + 1:] if cp >= 0 else sig).lstrip()
    if concl.startswith("∀"):
        rest, depth = concl[1:], 0
        for i, c in enumerate(rest):
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
            elif c == "," and depth == 0:
                region = (region + " " + rest[:i]).strip()
                break
    return _bracket_groups(region)


def _is_prenex(sig: str) -> bool:
    """Statement's conclusion opens with a `∀` binder prefix (un-∀ candidate)."""
    cp = _type_colon_pos(sig)
    return (sig[cp + 1:] if cp >= 0 else sig).lstrip().startswith("∀")


def _shared_binders(decls: "list[_Decl]") -> "list[str]":
    """Binder atoms appearing on ≥2 of `decls` (the file-wide hoist candidates),
    most-shared first."""
    from collections import Counter
    cnt: "Counter[str]" = Counter()
    for d in decls:
        for a in set(_binder_atoms(d.sig)):
            cnt[a] += 1
    return [a for a, c in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))
            if c >= 2]


_MATHLIB_CITE = re.compile(r"^(?:by\s+exact\s+)?([A-Za-z_][\w']*(?:\.[\w']+)+)(.*)$",
                           re.S)


def _pure_mathlib_citation(proof: str) -> "str | None":
    """If `proof` is a single dotted citation `Namespace.lemma args` (optionally
    `by exact …`) with NO tactic structure, return it without the `by exact`
    wrapper; else None. A `Library.…` head is a Library alias, not mathlib →
    None. The check that the head names a mathlib (not Library) decl is the
    caller's; here we only require a dotted head + a term-shaped tail."""
    s = " ".join(proof.split())
    m = _MATHLIB_CITE.match(s)
    if not m or m.group(1).startswith("Library."):
        return None
    if re.search(r"<;>|;|\bby\b|=>|\bfun\b|\bmatch\b|\bcalc\b", m.group(2)):
        return None
    return (m.group(1) + m.group(2)).rstrip()


def _explicit_param_names(sig: str) -> "list[str]":
    """Explicit `(name … : type)` binder names of `sig`, in caller order. (Inline
    substitution maps these to a consumer call's positional arguments.)"""
    names: "list[str]" = []
    for g in _binder_atoms(sig):
        if g.startswith("("):
            names += g[1:-1].split(":")[0].split()
    return names


def _take_args(s: str, k: int) -> "tuple[list[str], int]":
    """Read up to k application args from the start of `s` (the text after a head
    name). Each arg is a balanced (…)/[…]/{…} group or a bare atom; stops at a
    depth-0 terminator (`:=`, `,`, `;`, `)`, newline). Returns (args, consumed)."""
    args: "list[str]" = []
    i, n = 0, len(s)
    while len(args) < k and i < n:
        while i < n and s[i] in " \t":
            i += 1
        if i >= n or s[i] in ",;)\n" or (s[i] == ":" and s[i:i + 2] == ":="):
            break
        start, depth = i, 0
        while i < n:
            c = s[i]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and (c in " \t\n,;" or s[i:i + 2] == ":="):
                break
            i += 1
        args.append(s[start:i])
    return args, i


def _inline_wrapper_call(text: str, name: str, params: "list[str]",
                         body: str) -> "tuple[str, int]":
    """Replace every call `name <a1..an>` in `text` (n = len(params), NOT the
    decl header) with `(body[params→args])`. Bracket-aware arg read; whole-word
    param substitution. Partial applications (fewer than n args) are left alone.
    Returns (new_text, n_inlined). Build-gated by the caller — a bad substitution
    just fails the rebuild."""
    pat = re.compile(r"(?<![\w'.])" + re.escape(name) + r"(?![\w'])")
    pieces: "list[str]" = []
    pos, n_inlined = 0, 0
    for m in pat.finditer(text):
        if m.start() < pos:
            continue
        pre = text[max(0, m.start() - 12):m.start()]
        if re.search(r"\b(?:theorem|lemma|def)\s+$", pre):   # the decl header
            continue
        args, consumed = _take_args(text[m.end():], len(params))
        if len(args) != len(params) or not params:
            continue
        sub = body
        for p, a in zip(params, args):
            sub = re.sub(r"(?<![\w'])" + re.escape(p) + r"(?![\w'])",
                         lambda _m, a=a: a.strip(), sub)
        pieces.append(text[pos:m.start()])
        pieces.append(f"({sub})")
        pos = m.end() + consumed
        n_inlined += 1
    pieces.append(text[pos:])
    return "".join(pieces), n_inlined


def cite_drop_aliases(workspace: Path, problem: str,
                      scope: "list[_Decl]") -> "dict[str, str]":
    """Point 4 — DROP pure mathlib-alias wrappers (`cited` lifecycle) and inline
    every consumer to the mathlib lemma directly. A wrapper qualifies when its
    proof body is a single `Namespace.lemma args` citation (Namespace ≠ Library;
    `_pure_mathlib_citation`). For each, inline all calls across the problem's
    files (`_inline_wrapper_call`), drop the decl, and whole-file rebuild-gate
    every touched file — a failed inline keeps the wrapper (so the bridge that
    already cites mathlib stays; strict improvement). Returns {dropped_fqn:
    mathlib_head} for the DB. mathlib is already imported by every Library file,
    so no import is added."""
    cache: "dict[str, str]" = {}

    def gettext(rel: str) -> str:
        if rel not in cache:
            cache[rel] = (workspace / rel).read_text(encoding="utf-8")
        return cache[rel]

    rels = sorted({d.rel for d in scope})
    # cleanup just edited these files → their oleans are stale; the per-file gate
    # (`_build_file_copy_isolated`) imports siblings via olean, so rebuild first
    # or every gate fails (and cite-drop silently no-ops).
    from ...pipeline._lake import lake_build_modules
    try:
        mods = sorted({_mod_of_rel(r) for r in rels})
        lake_build_modules(workspace, mods)
        miss = [m.split(".")[-1] for m in _missing_oleans(workspace, mods)]
        if miss:
            print(f"[staged] cite-drop: oleans still missing after pre-flight: "
                  f"{miss}", flush=True)
    except Exception as e:  # noqa: BLE001 — best-effort pre-flight
        print(f"[staged] cite-drop: pre-flight build raised: {str(e)[:200]}",
              flush=True)
    cited: "dict[str, str]" = {}
    cands = 0
    for W in scope:
        body = decl_proof_body(gettext(W.rel), W.name)
        if not body:
            continue
        cite = _pure_mathlib_citation(body)
        if not cite:
            continue
        cands += 1
        params = _explicit_param_names(W.sig)
        edits: "dict[str, str]" = {}
        n_inlined = 0
        for rel in rels:
            nt, n = _inline_wrapper_call(gettext(rel), W.name, params, body)
            if n:
                edits[rel] = nt
                n_inlined += n
        dropped, removed = drop_decl(edits.get(W.rel, gettext(W.rel)), W.name)
        if not removed:
            continue
        edits[W.rel] = dropped
        # A reference the inliner could NOT rewrite (partial application — e.g.
        # polish un-∀'d the wrapper so consumers' k-arg calls now under-apply;
        # by design `_inline_wrapper_call` leaves those alone) must VETO the
        # drop: the gate below only builds touched files, so a survivor
        # reference in an untouched consumer would dangle and break the whole
        # problem at the bridge build (primary e2e 2026-06-10). Keep the
        # wrapper instead — it already cites mathlib, strict improvement.
        ref = re.compile(r"(?<![\w'.])" + re.escape(W.name) + r"(?![\w'])")
        leftover = [rel for rel in rels
                    if ref.search(edits.get(rel, gettext(rel)))]
        if leftover:
            print(f"[staged] cite-drop SKIP `{W.name}` (inlined {n_inlined}): "
                  f"references remain in {', '.join(r.rsplit('/', 1)[-1] for r in leftover)}",
                  flush=True)
            continue                              # keep wrapper (bridge stays)
        gate = [_build_file_copy_isolated(workspace, t) for t in edits.values()]
        if not all(ok for ok, _ in gate):
            why = next(d for ok, d in gate if not ok)
            print(f"[staged] cite-drop SKIP `{W.name}` (inlined {n_inlined}): "
                  f"gate failed: {why[-200:]}", flush=True)
            continue                              # keep wrapper (bridge stays)
        for rel, t in edits.items():
            (workspace / rel).write_text(t, encoding="utf-8")
            cache[rel] = t
        cited[W.fqn] = cite.split()[0]
        print(f"[staged] cite-drop `{W.name}` → inline {n_inlined} call(s) to "
              f"{cite.split()[0]}", flush=True)
    print(f"[staged] cite-drop: scanned {len(scope)} decls → {cands} pure-mathlib "
          f"candidate(s), {len(cited)} dropped", flush=True)
    return cited


def run_staged_cleanup_file(workspace: Path, problem: str, target_file: str, *,
                            scope_index: "list[tuple[str, str]] | None" = None,
                            prior_renames: "dict[str, str] | None" = None,
                            apply: bool = True, bridge: bool = True,
                            strip_comments: bool = False,
                            unused_args: bool = False,
                            decide: bool = False,
                            audit: bool = False,
                            simplify: bool = False,
                            conn=None,
                            pipeline_id: "str | None" = None) -> "dict":
    """§13 3c-2 per-file cleanup unit (the dispatcher's per-file work item).
    Clean ONE Library file: mark it → classify (with the cross-file chain guard
    from `prior_renames` = earlier files' {dropped_fqn: survivor_fqn}) → propose
    bridges → `_cleanup_one_file` (deferred-rewire: apply incoming renames from
    `prior_renames`, write ONLY this file). Returns
    `{dropped:{x:y}, merged:set, bridged:{x:y}, near, failed}` — the caller
    records drops to DB so later (consumer) files self-apply them.

    Generic stage shell (P2-ready): the dedup stage is active; decl-cleanup +
    per-file build (e) are P2 hooks inside `_cleanup_one_file`. Same per-decl
    logic as the serial `run_staged_cleanup`, one file at a time."""
    prior_renames = dict(prior_renames or {})
    scope, pool = _load_decls(workspace, problem, scope_index, conn=conn)
    by_fqn = {d.fqn: d for d in (*pool, *scope)}
    decls_in_file = [d for d in scope if d.rel == target_file]
    # FREEZE Defs-origin decls: anything declared in Problems/<p>/Defs.lean is
    # the problem's CANONICAL definition — migrate's Gate D pinned it def-eq, and
    # cleanup must not undo that. The stages that *act on* their decl list
    # (dedup-drop/bridge, simplify, decide-rename) skip these names; audit KEEPS
    # them in its list so its own gate still fails any rename/delete (a missing
    # decl can't #check), and an audit.md note tells the agent to reproduce them
    # verbatim. (User: "Defs 來的東西禁止任何改動".)
    from . import inventory as _inv
    defs_names = set(_inv.defs_decls(workspace, problem))
    empty = {"dropped": {}, "merged": set(), "bridged": {}, "near": [], "failed": []}
    if not decls_in_file:
        return empty
    scope_by_leaf = {d.name: d for d in scope}
    all_by_leaf = {d.name: d for d in (*pool, *scope)}
    prompt_path = workspace / "Tooling" / "prompts" / "librarian" / "dedup_audit.md"
    problem_dir = workspace.joinpath("Problems", *problem.split("."))
    import time as _tm
    _t = _tm.perf_counter
    _T = {"0": _t()}
    pairs, log = _audit_one_file(workspace, problem, target_file, scope, pool,
                                 scope_by_leaf, all_by_leaf, prompt_path, problem_dir)
    print(log, flush=True)
    _T["mark"] = _t()
    plan, _skipped = _classify_pairs(
        workspace, problem, sorted(set(pairs)), scope_index=scope_index,
        prior_dropped=set(prior_renames),
        prior_survivors=set(prior_renames.values()), conn=conn)
    # Never drop/bridge a Defs-origin decl (freeze): a bridge would replace the
    # canonical definition with a one-liner alias, a drop would delete it.
    for _x in [x for x in plan if x.rsplit(".", 1)[-1] in defs_names]:
        plan.pop(_x, None)
    if not apply:
        return {**empty,
                "dropped": {x: Y.fqn for x, (Y, k) in plan.items() if k == "drop"},
                "near": [(x, Y.fqn) for x, (Y, k) in plan.items() if k == "bridge"]}
    bridge_pairs = [(x, Y.fqn) for x, (Y, k) in plan.items() if k == "bridge"]
    bridges = (_propose_bridges(workspace, problem, bridge_pairs, conn=conn,
                                scope_index=scope_index)
               if (bridge and bridge_pairs) else {})
    rename_map = [(_decl_from_fqn(xf, by_fqn), _decl_from_fqn(yf, by_fqn))
                  for xf, yf in prior_renames.items()]
    r = _cleanup_one_file(workspace, target_file, decls_in_file, plan, bridges,
                          rename_map, _Splicer(workspace))
    _T["dedup"] = _t()
    for xf, Yd in r["drops"].items():
        tag = "merged" if xf in r["merged"] else "dropped"
        print(f"[staged] {tag} {xf.rsplit('.', 1)[-1]} → cite {Yd.name}", flush=True)
    for xf, Yd in r["bridged"]:
        print(f"[staged] bridged {xf.rsplit('.', 1)[-1]} → cite {Yd.name}", flush=True)
    # Survivors of this file's dedup pass: not dropped, not bridged (bridges are
    # already one-liners). The (c) simplify + (e) docstring passes run on these.
    bridged_fqns = {x for x, _ in r["bridged"]}
    # `survivor_decls` drives simplify (proof-body rewrite): exclude Defs so a
    # `def` body is never simplified (frozen + #38 cross-decl risk).
    survivor_decls = [d for d in decls_in_file
                      if d.fqn not in r["drops"] and d.fqn not in bridged_fqns
                      and d.name not in defs_names]
    # Everything still PRESENT in the file = survivors + bridged aliases. The
    # whole-file agentic stages (decide/audit) must gate on THIS set, not
    # `survivor_decls`: a bridged alias is a one-liner a zealous reviewer happily
    # deletes, and a #check gate that doesn't list it never notices — the alias
    # vanishes green and every consumer citing it dangles (rcf audit e2e
    # 2026-06-10: audit deleted the bridged `block_companion`; the keystone file
    # then failed its own baseline snapshot and the bridge build went red).
    present_decls = [d for d in decls_in_file if d.fqn not in r["drops"]]
    # (c) decl-cleanup — per-decl proof simplification (marked-only). Sig-
    # preserving → no consumer rewrite. Runs BEFORE docstrings (§13 order).
    n_simplified = 0
    if simplify and survivor_decls:
        marked = _mark_simplify_file(
            workspace, problem, target_file,
            [d.name for d in survivor_decls],
            workspace.joinpath("Problems", *problem.split(".")))
        n_simplified = decl_cleanup_simplify_file(
            workspace, problem, target_file, survivor_decls, marked,
            conn=conn, pipeline_id=pipeline_id)
    _T["simplify"] = _t()
    # (c) unused-arg removal — drop signature hypotheses unused in the type
    # (mathlib `unusedArguments`). Mechanical, type-CHANGING (rebuild-gated, not
    # #check); v1 = `[…]` instance binders (consumer-safe). Runs BEFORE variable
    # extraction so it doesn't hoist a binder about to be deleted.
    unused_removed = False
    if unused_args and survivor_decls:
        unused_removed = file_cleanup_unused_args(
            workspace, problem, target_file, survivor_decls)
        # `_`-prefix hypothesis binders the `unusedVariables` lint flags (unused
        # in the BODY — orthogonal to unused_args' type-unused instance binders).
        # Mechanical, in ONE rebuild, BEFORE decide/audit — so the audit agent
        # doesn't spend its whole 960s budget `_`-prefixing 12+ binders one slow
        # LSP round-trip at a time on a big file (residue SimplyConnectedIntegral /
        # LaurentDecompOuter STALL root cause, 2026-06-19).
        file_cleanup_underscore_unused_hyps(workspace, problem, target_file,
                                            frozen=defs_names)
    _T["unused"] = _t()
    # (c2) normalize whitespace + empty lines — the text-based mathlib style
    # linters (linter.style.whitespace / .emptyLine) that fire ONLY on a real
    # module build (not the cold gate's throwaway), so the per-file zero-warning
    # gate misses them but the audit agent's LSP `errors_at` surfaces them and it
    # burns its whole 960s budget hand-fixing 100+ `(0:ℝ)`→`(0 : ℝ)` spacings one
    # ~25s round-trip at a time → times out (residue HomotopyIntegral 141+4 → all
    # 3 audit cold passes hit the cap, 2026-06-20). Mechanical + rebuild-gated,
    # only when audit will run (its whole purpose is to relieve the agent).
    if audit:
        file_cleanup_normalize_whitespace(workspace, problem, target_file,
                                          frozen=defs_names)
    _T["whitespace"] = _t()
    # (e) strip framework-process `--` comments (entry_kind / sub-goal / Closer:
    # / combinator / (was: …)) migrate carried from the proof. Mechanical,
    # comment-only. Before decide/audit so the agent sees a clean file.
    # ONE file-level gateway session spans the mechanical whole-file gates
    # (strip-comments _lake_check + decide degrade-ladder _build_file_copy_
    # isolated): both verify whole-file candidates whose import closure is this
    # file's, so they reuse a single warm CLAIMED slot — the first didChange
    # loads the closure (~25s), every later gate is a ~4-5s body re-elaborate
    # instead of a fresh cold `lake env lean` (#35). Held ONLY across this
    # mechanical span: simplify already released its per-decl agent sessions and
    # audit registers its own after, so this never holds a 2nd slot at once
    # (preserves the dispatch.pool == workers invariant). token=None (no gateway
    # / pool full / standalone CLI / tests) → every gate runs cold, never blocks.
    from ...lsp import lifecycle as _gw
    _mech_token = None
    if strip_comments or (decide and present_decls):
        _mech_token = _gw.register_session(
            pipeline_id=f"cleanup-mech:{problem}:{target_file}",
            target_path=workspace / target_file,
            problem=problem, workspace=workspace)
    renamed: dict[str, str] = {}
    imports_min = False
    try:
        if strip_comments:
            file_cleanup_strip_framework_comments(
                workspace, problem, target_file, session_token=_mech_token)
        # (P4) decide — LAST agentic step, on the cleaned shape: align kept
        # survivors' names to mathlib conventions + swap the `import Mathlib`
        # umbrella for a precise canonical set. Mechanical apply + per-file
        # rebuild gate (degrade ladder: bad imports never cost a rename);
        # consumers self-apply renames via deferred-rewire (caller records
        # {old:new}).
        # decide renames only the decls in its list → exclude Defs (frozen: a
        # rename would desync the Library name from the problem's Defs.lean).
        decide_decls = [d for d in present_decls if d.name not in defs_names]
        if decide and decide_decls:
            renamed, imports_min = file_cleanup_decide(
                workspace, problem, target_file, decide_decls,
                scope=scope, pool=pool, session_token=_mech_token)
    finally:
        if _mech_token:
            _gw.release_session(_mech_token)
    _T["decide"] = _t()
    # (final) audit — free whole-file mathlib review on the decided shape. Its
    # declared renames join decide's; a CHAIN (decide A→B, audit B→C) collapses
    # to A→C so the caller's slug lookup (keyed by the migrate-time fqn) and the
    # consumers' deferred-rewire both see one hop.
    audited = False
    if audit and present_decls:
        post_decide = [
            d._replace(name=renamed[d.fqn].rsplit(".", 1)[-1],
                       fqn=renamed[d.fqn]) if d.fqn in renamed else d
            for d in present_decls]
        audit_renames, audited = file_cleanup_audit(
            workspace, problem, target_file, post_decide,
            scope=scope, pool=pool, conn=conn, pipeline_id=pipeline_id,
            frozen=defs_names)
        inv = {v: k for k, v in renamed.items()}
        for o, n in audit_renames.items():
            renamed[inv.get(o, o)] = n
    _T["audit"] = _t()
    print(f"[staged-timing] {target_file.split('/')[-1]}: "
          f"mark={_T['mark']-_T['0']:.0f}s dedup={_T['dedup']-_T['mark']:.0f}s "
          f"simplify={_T['simplify']-_T['dedup']:.0f}s "
          f"unused={_T['unused']-_T['simplify']:.0f}s "
          f"whitespace={_T['whitespace']-_T['unused']:.0f}s "
          f"decide={_T['decide']-_T['whitespace']:.0f}s "
          f"audit={_T['audit']-_T['decide']:.0f}s "
          f"total={_T['audit']-_T['0']:.0f}s", flush=True)
    return {"dropped": {x: Yd.fqn for x, Yd in r["drops"].items()},
            "merged": set(r["merged"]),
            "bridged": {x: Yd.fqn for x, Yd in r["bridged"]},
            "near": r["near"], "failed": r["failed"],
            "simplified": n_simplified, "unused_removed": unused_removed,
            "renamed": renamed,
            "imports_min": imports_min, "audited": audited}


def run_file_audit_dedup(workspace: Path, problem: str, *, apply: bool = False,
                         bridge: bool = True, concurrency: int = 4,
                         scope_index: "list[tuple[str, str]] | None" = None,
                         conn=None) -> "dict":
    """Legacy batch gate (pre-§13): per-file audit marking → batch mechanical
    gate (`apply_llm_pairs` whole-problem rebuild + batch bridger). Kept for the
    standalone `--audit` CLI; the chain uses `run_staged_cleanup`."""
    uniq, _scope, _pool = _collect_marked_pairs(
        workspace, problem, concurrency=concurrency, scope_index=scope_index,
        conn=conn)
    res = apply_llm_pairs(workspace, problem, uniq, apply=apply,
                          scope_index=scope_index, conn=conn)
    result = {**res, "proposed": len(uniq), "bridged": {}, "bridge_failed": []}
    if apply and res["near"] and bridge:
        br = run_llm_bridge(workspace, problem, res["near"], apply=apply,
                            scope_index=scope_index, conn=conn)
        result["bridged"] = br.get("bridged", {})
        result["bridge_failed"] = br.get("failed", [])
    return result


if __name__ == "__main__":
    import json
    import sys
    ws = Path(".").resolve()
    prob = sys.argv[1] if len(sys.argv) > 1 else ""
    do_apply = "--apply" in sys.argv
    if "--thin" in sys.argv:                      # mechanical thin-wrapper scan
        rows = find_thin_wrappers(ws, prob)
        deleg = [(f, p, c) for f, p, c in rows if c]
        auto = [(f, p, c) for f, p, c in rows if not c]
        print(f"=== thin wrappers in {prob}: {len(rows)} "
              f"({len(deleg)} delegating, {len(auto)} automation) ===")
        for f, p, c in deleg:
            print(f"  [cite {c}]  {f.rsplit('.', 1)[-1]}  ::=  {p}")
        for f, p, c in auto:
            print(f"  [auto]  {f.rsplit('.', 1)[-1]}  ::=  {p}")
    elif "--staged" in sys.argv:                  # §13 staged per-decl pipeline
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) \
            if "--jobs" in sys.argv else 4
        res = run_staged_cleanup(ws, prob, apply=do_apply,
                                 bridge="--no-bridge" not in sys.argv,
                                 concurrency=jobs)
        bridged = res.get("bridged", {})
        merged = res.get("merged", set())
        ndrop = len(res["dropped"]) - len(merged)
        print(f"\n=== staged-cleanup {'APPLIED' if do_apply else 'DRY'} on {prob}: "
              f"{ndrop} drop, {len(merged)} merge, {len(bridged)} bridge, "
              f"{len(res['near'])} near, {len(res['skipped'])} skip, "
              f"{len(res.get('bridge_failed', []))} bridge-fail "
              f"(of {res.get('proposed', 0)} verdict-pairs) ===")
        for x, y in res["dropped"].items():
            kind = "merge" if x in merged else "drop "
            print(f"  {kind}  {x.rsplit('.', 1)[-1]}  →  cite {y.rsplit('.', 1)[-1]}")
        for x, y in bridged.items():
            print(f"  bridge {x.rsplit('.', 1)[-1]}  →  cite {y.rsplit('.', 1)[-1]}")
    elif "--audit" in sys.argv:                   # per-file audit marker → gate
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) \
            if "--jobs" in sys.argv else 4
        res = run_file_audit_dedup(ws, prob, apply=do_apply,
                                   bridge="--no-bridge" not in sys.argv,
                                   concurrency=jobs)
        merged = res.get("merged", set())
        bridged = res.get("bridged", {})
        ndrop = len(res["dropped"]) - len(merged)
        print(f"\n=== dedup-audit {'APPLIED' if do_apply else 'DRY'} on {prob}: "
              f"{ndrop} drop, {len(merged)} merge, {len(bridged)} bridge, "
              f"{len(res['near'])} near, {len(res['skipped'])} skip "
              f"(of {res.get('proposed', 0)} verdict-pairs) ===")
        for x, y in res["dropped"].items():
            kind = "merge" if x in merged else "drop "
            print(f"  {kind}  {x.rsplit('.', 1)[-1]}  →  cite {y.rsplit('.', 1)[-1]}")
        for x, y in bridged.items():
            print(f"  bridge {x.rsplit('.', 1)[-1]}  →  cite {y.rsplit('.', 1)[-1]}")
    elif "--pairs" in sys.argv:                   # 3.1a on LLM-marked pairs
        pf = sys.argv[sys.argv.index("--pairs") + 1]
        marked = json.loads(Path(pf).read_text(encoding="utf-8"))
        pairs = [(p["x"], p["y"]) for p in marked]
        res = apply_llm_pairs(ws, prob, pairs, apply=do_apply)
        print(f"\n=== dedup-llm {'APPLIED' if do_apply else 'DRY'} on {prob}: "
              f"{len(res['dropped'])} drop(s), {len(res['near'])} near, "
              f"{len(res['skipped'])} skipped ===")
        for x, y in res["dropped"].items():
            print(f"  drop {x.rsplit('.', 1)[-1]}  →  cite {y.rsplit('.', 1)[-1]}")
        for x, y in res["near"]:
            print(f"  near {x.rsplit('.', 1)[-1]}  ~  {y.rsplit('.', 1)[-1]}  (3.1b)")
    else:                                          # v1a mechanical pass
        res = run_dedup_campaign(ws, prob, apply=do_apply)
        print(f"\n=== dedup {'APPLIED' if do_apply else 'DRY'} on {prob}: "
              f"{len(res)} drop(s) ===")
        for x, y in res.items():
            print(f"  drop {x.rsplit('.', 1)[-1]}  →  cite {y.rsplit('.', 1)[-1]}")
