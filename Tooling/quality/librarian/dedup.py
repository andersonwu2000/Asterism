"""PHASE 3 cleanup-dedup (v1a, mechanical) — see docs/internal/librarian_cleanup.md §7.

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
import subprocess
import uuid
from pathlib import Path
from typing import NamedTuple

from .. import dedupe as _dd


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

_BATCH_TIMEOUT_SEC = 240
# Max pairs per `lake env lean` invocation. A giant single file over-reports
# True: Lean stops elaborating past an internal error threshold, so pairs
# beyond it produce no error line and are mis-marked defeq (courant dry-run
# 2026-06-06: 23 false hits in one ~1000-pair batch; n=1/n=2 were correct).
# Chunking keeps each file small enough for reliable per-pair attribution.
_BATCH_MAX_PAIRS = 40


def _type_colon_pos(sig: str) -> int:
    """Index of the type colon in `<binders> : <conclusion>` — the FIRST
    depth-0 `:`. Binder colons (`(x : T)`, `{n : ℕ}`) are bracketed
    (depth > 0); the conclusion's own colons (`∃ x : E, …`, `fun y : T =>`)
    come AFTER. `dedupe._to_forall_form` / `_conclusion_of_signature` split
    on the LAST depth-0 colon and so mangle ∃/∀/fun-bearing conclusions —
    this splitter is correct for the defeq probe."""
    dp = db = dk = da = 0
    for i, c in enumerate(sig):
        if c == "(":
            dp += 1
        elif c == ")":
            dp -= 1
        elif c == "{":
            db += 1
        elif c == "}":
            db -= 1
        elif c == "[":
            dk += 1
        elif c == "]":
            dk -= 1
        elif c == "⦃":
            da += 1
        elif c == "⦄":
            da -= 1
        elif c == ":" and dp == db == dk == da == 0:
            return i
    return -1


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
    if seen_modules:
        from ...pipeline._lake import lake_build_modules
        try:
            lake_build_modules(workspace, sorted(seen_modules))
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

    tmp_dir = workspace / ".attempts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_dir / f"_dedup_defeq_{uuid.uuid4().hex}.lean"
    tmp_file.write_text(content, encoding="utf-8")
    try:
        r = subprocess.run(
            ["lake", "env", "lean", str(tmp_file)], cwd=str(workspace),
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=_BATCH_TIMEOUT_SEC)
        output = r.stdout + r.stderr
        rc = r.returncode
    except (subprocess.TimeoutExpired, OSError):
        return [False] * len(pairs)
    finally:
        try:
            tmp_file.unlink()
        except OSError:
            pass

    error_lines = {int(m.group(1)) for m in _dd._LAKE_ERR_RE.finditer(output)}
    if not error_lines:
        return [True] * len(pairs) if rc == 0 else [False] * len(pairs)
    in_pair = set()
    for el in error_lines:
        for i, start in enumerate(pair_start_lines):
            end = (pair_start_lines[i + 1] - 1
                   if i + 1 < len(pair_start_lines) else len(lines))
            if start <= el <= end:
                in_pair.add(el)
                break
    if error_lines - in_pair:        # global error → refuse all
        return [False] * len(pairs)
    results = []
    for i, start in enumerate(pair_start_lines):
        end = (pair_start_lines[i + 1] - 1
               if i + 1 < len(pair_start_lines) else len(lines))
        results.append(not any(start <= el <= end for el in error_lines))
    return results


def _code_spans(text: str) -> list[tuple[int, int]]:
    """`(start, end)` of CODE regions — everything outside Lean comments.
    Handles `--` line comments and `/- … -/` block comments (nestable, which
    also covers `/-- … -/` docstrings). Comment markers inside string
    literals are not special-cased (rare in proof source; build-gated)."""
    spans: list[tuple[int, int]] = []
    i, n = 0, len(text)
    code_start = 0
    while i < n:
        c = text[i]
        if c == "-" and i + 1 < n and text[i + 1] == "-":
            spans.append((code_start, i))
            j = text.find("\n", i)
            i = n if j < 0 else j
            code_start = i
        elif c == "/" and i + 1 < n and text[i + 1] == "-":
            spans.append((code_start, i))
            depth = 1
            i += 2
            while i < n and depth > 0:
                if text[i] == "/" and i + 1 < n and text[i + 1] == "-":
                    depth += 1
                    i += 2
                elif text[i] == "-" and i + 1 < n and text[i + 1] == "/":
                    depth -= 1
                    i += 2
                else:
                    i += 1
            code_start = i
        else:
            i += 1
    spans.append((code_start, n))
    return spans


def replace_token(text: str, old: str, new: str) -> tuple[str, int]:
    """Replace whole-token occurrences of `old` with `new`, in CODE regions
    only. `old` may be a bare name (`col_sum_collapse`) or a dotted FQN
    (`Library.X.col_sum_collapse`). Boundaries treat `[A-Za-z0-9_'.]` as
    identifier chars, so:
      - a bare `old` does NOT match `A.old` (FQN tail / projection) or
        `oldx` / `xold`;
      - an FQN `old` does NOT match when followed by a further `.comp`.
    Returns `(new_text, n_replacements)`.
    """
    pat = re.compile(r"(?<![\w'.])" + re.escape(old) + r"(?![\w'.])")
    spans = _code_spans(text)
    out: list[str] = []
    total = 0
    last = 0
    for s, e in spans:
        out.append(text[last:s])          # comment gap — verbatim
        seg, k = pat.subn(new, text[s:e])
        out.append(seg)
        total += k
        last = e
    out.append(text[last:])
    return "".join(out), total


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

def _block_start(text: str, header_pos: int) -> int:
    """Char offset of the start of `header_pos`'s decl block — walks back
    over the contiguous doc-comment lines (`--` and `/- … -/`) directly
    above the header, stopping at a blank-line separator or a code line."""
    ls = text.rfind("\n", 0, header_pos) + 1   # start of header's line
    in_block = False
    while ls > 0:
        pls = text.rfind("\n", 0, ls - 1) + 1   # start of previous line
        line = text[pls:ls - 1]
        s = line.strip()
        if in_block:
            ls = pls
            if "/-" in line:
                in_block = False
            continue
        if s == "":
            break                                # blank separator → stop
        if s.startswith("--"):
            ls = pls
            continue
        if s.startswith("/-") and s.endswith("-/"):
            ls = pls                             # self-contained block comment
            continue                             # (single-line /-- … -/)
        if s.endswith("-/"):
            in_block = True                      # end of a multi-line block
            ls = pls
            continue
        break                                    # code line → stop
    return ls


_DECL_NAME_RE = re.compile(
    r"(?m)^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
    r"(?:private[ \t]+|protected[ \t]+|noncomputable[ \t]+|scoped[ \t]+)*"
    r"(?:theorem|lemma|def)[ \t]+([A-Za-z_][\w'.]*)")


def decl_span(text: str, name: str) -> "tuple[int, int] | None":
    """`(start, end)` char span of decl `name`'s full block (leading
    comment + decl), suitable for removal. `end` is the next decl block's
    start, or the `end <namespace>` line, or EOF. None if `name` absent."""
    heads = list(_DECL_NAME_RE.finditer(text))
    idx = next((i for i, m in enumerate(heads) if m.group(1) == name), None)
    if idx is None:
        return None
    start = _block_start(text, heads[idx].start())
    if idx + 1 < len(heads):
        end = _block_start(text, heads[idx + 1].start())
    else:
        m = re.search(r"(?m)^end\b", text[heads[idx].start():])
        end = (heads[idx].start() + m.start()) if m else len(text)
    return start, end


def drop_decl(text: str, name: str) -> "tuple[str, bool]":
    """Remove decl `name`'s block from `text`. Returns `(new_text, removed)`."""
    span = decl_span(text, name)
    if span is None:
        return text, False
    s, e = span
    return text[:s] + text[e:], True


# ---------------------------------------------------------------------
# replace_proof — collapse a near-dup's proof to a one-line bridge (v1b-②)
#
# A `near` pair (X defeq-ish to Y but not drop-in substitutable at call sites,
# so X cannot be dropped) is deduped by replacing X's *proof* with a one-liner
# citing Y, keeping X's statement intact → consumers are untouched. Kills the
# duplicated reasoning, keeps the interface. Build-gated (apply_bridge).
# ---------------------------------------------------------------------

def _proof_assign_pos(text: str, header_start: int) -> int:
    """Char index of the proof `:=` for the decl whose header starts at
    `header_start` — the first depth-0 `:=` after it. Binder/type `:=`
    (structure-instance `{f := v}`) sit at depth > 0; the proof assignment is
    the first at depth 0. Comment-borne `:=` are not special-cased (rare in a
    binder/type; build-gated)."""
    dp = db = dk = da = 0
    i, n = header_start, len(text)
    while i < n - 1:
        c = text[i]
        if c == "(":
            dp += 1
        elif c == ")":
            dp -= 1
        elif c == "{":
            db += 1
        elif c == "}":
            db -= 1
        elif c == "[":
            dk += 1
        elif c == "]":
            dk -= 1
        elif c == "⦃":
            da += 1
        elif c == "⦄":
            da -= 1
        elif c == ":" and text[i + 1] == "=" and dp == db == dk == da == 0:
            return i
        i += 1
    return -1


def replace_proof(text: str, name: str, new_proof: str) -> "tuple[str, bool]":
    """Replace decl `name`'s proof (everything from its `:=`) with
    `:= <new_proof>`, leaving the header/signature and the trailing blank
    lines intact. Returns `(new_text, replaced)`."""
    heads = list(_DECL_NAME_RE.finditer(text))
    idx = next((i for i, m in enumerate(heads) if m.group(1) == name), None)
    if idx is None:
        return text, False
    span = decl_span(text, name)
    if span is None:
        return text, False
    _, block_end = span
    assign = _proof_assign_pos(text, heads[idx].start())
    if assign < 0 or assign >= block_end:
        return text, False
    pe = block_end                       # trim trailing whitespace → preserve it
    while pe > assign and text[pe - 1] in " \t\r\n":
        pe -= 1
    return text[:assign] + f":= {new_proof}" + text[pe:], True


def decl_proof_body(text: str, name: str) -> "str | None":
    """The proof body of decl `name` — everything after its `:=`, trimmed —
    or None if absent. Used by the wrapper-merge to move a real proof onto a
    thin-wrapper survivor."""
    heads = list(_DECL_NAME_RE.finditer(text))
    idx = next((i for i, m in enumerate(heads) if m.group(1) == name), None)
    if idx is None:
        return None
    span = decl_span(text, name)
    if span is None:
        return None
    _, end = span
    assign = _proof_assign_pos(text, heads[idx].start())
    if assign < 0 or assign >= end:
        return None
    return text[assign + 2:end].strip()


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


def _mod_of_rel(rel: str) -> str:
    return rel.replace("\\", "/")[:-5].replace("/", ".")  # strip .lean


def _parse_index(workspace: Path) -> "dict[str, list[tuple[str, str]]]":
    out: dict[str, list[tuple[str, str]]] = {}
    cur = None
    try:
        text = (workspace / "Library" / "INDEX.md").read_text(encoding="utf-8")
    except OSError:
        return out
    for ln in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", ln)
        if m:
            cur = m.group(1).strip()
            out[cur] = []
            continue
        m = _dd._LIB_INDEX_ENTRY_RE.match(ln.strip())
        if m and cur is not None:
            out[cur].append((m.group(1), m.group(2).strip()))
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


class _Decl(NamedTuple):
    fqn: str
    rel: str
    module: str
    name: str
    sig: str
    binders: int
    concl_tokens: "frozenset[str]"


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


def _update_index(workspace: Path, dropped_fqns: "set[str]") -> None:
    idx = workspace / "Library" / "INDEX.md"
    try:
        lines = idx.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return
    kept = []
    for ln in lines:
        m = _dd._LIB_INDEX_ENTRY_RE.match(ln.strip())
        if m and m.group(1) in dropped_fqns:
            continue
        kept.append(ln)
    idx.write_text("".join(kept), encoding="utf-8")


def _load_decls(workspace: Path, problem: str
                ) -> "tuple[list[_Decl], list[_Decl]]":
    """(scope decls for `problem`, domain pool decls). Both theorem/lemma
    with parseable sigs."""
    domain = problem.split(".")[0] if "." in problem else problem
    index = _parse_index(workspace)
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

    scope = [d for d in (decl(f, r) for f, r in index.get(problem, [])) if d]
    pool: list[_Decl] = []
    for ents in index.values():
        for f, r in ents:
            parts = r.replace("\\", "/").split("/")
            if len(parts) >= 2 and parts[0] == "Library" and parts[1] == domain:
                d = decl(f, r)
                if d:
                    pool.append(d)
    return scope, pool


def _external_consumer(workspace: Path, X: _Decl,
                       scope_rels: "set[str]") -> "str | None":
    """Return the rel-path of a Library file OUTSIDE the scope problem that
    references decl X (by fqn, or by bare name while importing X's module),
    or None. v1a only rewrites/rebuilds the scope problem's files, so a decl
    with a CROSS-PROBLEM consumer must NOT be dropped here (the scope-only
    build gate wouldn't catch the breakage) — it's deferred to v1b's
    cross-problem rewire. Cross-problem Library→Library refs are real
    (e.g. NormalDiagonalization→SchurTriangularization, RCF→InvariantFactor)."""
    lib = workspace / "Library"
    for f in lib.rglob("*.lean"):
        rel = f.relative_to(workspace).as_posix()
        if rel in scope_rels:
            continue
        try:
            t = f.read_text(encoding="utf-8")
        except OSError:
            continue
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
            if _mod_of_rel(rel) != Y.module and Y.fqn in t:
                t = _ensure_import(t, Y.module)
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
    statement so consumers are untouched (the v1b-② near-dup move). Ensure the
    import of Y's module, then build the problem's modules → keep on success,
    else restore the snapshot. Returns True iff committed."""
    from ...pipeline._lake import lake_build_modules
    snap = {}
    for rel in scope_rels:
        try:
            snap[rel] = (workspace / rel).read_text(encoding="utf-8")
        except OSError:
            return False
    try:
        new_t, ok = replace_proof(snap[X.rel], X.name, bridge)
        if not ok:
            return False
        if _mod_of_rel(X.rel) != Y.module:
            new_t = _ensure_import(new_t, Y.module)
        (workspace / X.rel).write_text(new_t, encoding="utf-8")
        prob_modules = sorted({_mod_of_rel(r) for r in scope_rels})
        ok2, _msg = lake_build_modules(workspace, prob_modules)
        if ok2:
            return True
    except Exception:  # noqa: BLE001
        pass
    for rel, t in snap.items():       # revert
        (workspace / rel).write_text(t, encoding="utf-8")
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
            if _mod_of_rel(rel) != Y.module and Y.fqn in t:
                t = _ensure_import(t, Y.module)
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


def run_dedup_campaign(workspace: Path, problem: str, *, apply: bool = False
                       ) -> "dict[str, str]":
    """Mechanical dedup over `problem`'s Library decls (v1a). Returns
    {dropped_fqn: survivor_fqn}. `apply=False` = dry-run (detect only)."""
    from ...pipeline._lake import lake_build_modules
    scope, pool = _load_decls(workspace, problem)
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
        _update_index(workspace, set(dropped))
    return dropped


# ---------------------------------------------------------------------
# v1b — LLM dedup layer (standalone, operator/Agent-orchestrated)
#
# v1a's mechanical pass only tests pairs that survive a token-Jaccard
# pre-filter (≥0.5), which misses exact dups stated with different tokens
# (renamed binders, reformulated conclusions). v1b-① adds a 3.0 LLM
# wide-marking pass: the marker scans `mark_context` (every scope decl +
# the domain pool) at high recall and proposes candidate pairs; those feed
# the SAME mechanical exact-defeq gate (`batch_defeq` → `_apply_drop`,
# rewire-or-revert). Pairs the marker flagged but that are NOT defeq are the
# 3.1b near-dup tier (one-line bridge — separate increment).
#
# The LLM step is operator/Agent-driven (this stays DB-free + spawn-free):
# `mark_context` → marker Agent returns pairs → `apply_llm_pairs`. Python
# proposes nothing semantic; it only mechanically validates + gates, exactly
# as the framework's proposer/validator split.
# ---------------------------------------------------------------------

def mark_context(workspace: Path, problem: str) -> str:
    """Compact `<fqn> :: <signature>` listing for the 3.0 wide-marking pass:
    every scope decl (dedup candidates) then the domain pool (potential
    twins/survivors). Pure — reads the Library, no lake."""
    scope, pool = _load_decls(workspace, problem)

    def row(d: _Decl) -> str:                  # one line per decl
        return f"{d.fqn} :: {' '.join(d.sig.split())}"

    lines = [f"# dedup marking — {problem}",
             f"# SCOPE ({len(scope)} decls) — propose to drop these if a twin exists:"]
    lines += [row(d) for d in sorted(scope, key=lambda d: d.fqn)]
    lines.append(f"# POOL ({len(pool)} decls) — potential survivors/twins:")
    lines += [row(d) for d in sorted(pool, key=lambda d: d.fqn)]
    return "\n".join(lines)


def apply_llm_pairs(workspace: Path, problem: str,
                    pairs: "list[tuple[str, str]]", *, apply: bool = False
                    ) -> "dict":
    """3.0→3.1a: run LLM-marked candidate pairs `(x_fqn dups y_fqn)` through
    the mechanical exact-defeq gate. `x` must be a scope decl; `y` any domain
    decl. A pair lands a DROP only when x≡y (defeq), y is the deterministic
    survivor, and x has no cross-problem consumer — then drop x + rewire
    (rewire-or-revert), identical to v1a. Returns
    `{'dropped': {x:y}, 'near': [(x,y)], 'skipped': [(x,y)]}`; `near` =
    marked but not defeq → the 3.1b bridger's input."""
    scope, pool = _load_decls(workspace, problem)
    by_fqn = {d.fqn: d for d in (*pool, *scope)}   # scope wins name clashes
    scope_fqns = {d.fqn for d in scope}
    scope_rels = sorted({d.rel for d in scope})

    # Resolve + validate pairs. batch_defeq builds the canonical oleans it
    # imports (pre-flight) and _apply_drop builds the scope modules, so no
    # top-level pool build is needed; with no valid pair we touch no lake.
    probe: list[tuple[str, str, str]] = []
    pair_decls: list[tuple[_Decl, _Decl]] = []
    skipped: list[tuple[str, str]] = []
    for x_fqn, y_fqn in pairs:
        X, Y = by_fqn.get(x_fqn), by_fqn.get(y_fqn)
        if X is None or Y is None or x_fqn not in scope_fqns or x_fqn == y_fqn:
            skipped.append((x_fqn, y_fqn))
            continue
        probe.append((X.sig, Y.module, Y.fqn))
        pair_decls.append((X, Y))
    flags = batch_defeq(workspace, problem, probe) if probe else []

    dropped: dict[str, str] = {}
    merged: set[str] = set()
    near: list[tuple[str, str]] = []
    for (X, Y), ok in zip(pair_decls, flags):
        if not ok:
            near.append((X.fqn, Y.fqn))
            continue
        if X.fqn in dropped:
            continue
        if _survivor(X.fqn, Y.fqn) != Y.fqn:
            skipped.append((X.fqn, Y.fqn))      # x is the better survivor
            continue
        if _external_consumer(workspace, X, set(scope_rels)):
            skipped.append((X.fqn, Y.fqn))      # cross-problem consumer → v1b-c
            continue
        if not apply:
            dropped[X.fqn] = Y.fqn
            continue
        if _apply_drop(workspace, scope_rels, X, Y):
            dropped[X.fqn] = Y.fqn
            print(f"[dedup-llm] dropped {X.name} → cite {Y.name}", flush=True)
        elif apply_merge(workspace, scope_rels, X, Y):
            dropped[X.fqn] = Y.fqn               # wrapper-merge (moved proof)
            merged.add(X.fqn)
            print(f"[dedup-llm] merged {X.name} → {Y.name} (moved real proof)",
                  flush=True)
        else:
            near.append((X.fqn, Y.fqn))         # genuine near → LLM bridger
    if apply and dropped:
        _update_index(workspace, set(dropped))
    return {"dropped": dropped, "merged": merged, "near": near,
            "skipped": skipped}


def _strip_json_fence(text: str) -> str:
    """Drop a leading ```json / trailing ``` fence if the agent wrapped its
    array (the classify runner tolerates the same — `_load_json`)."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[A-Za-z0-9]*\n", "", t)
        t = re.sub(r"\n?```$", "", t.strip())
    return t.strip()


def parse_dedup_pairs(text: str
                      ) -> "tuple[list[tuple[str, str]] | None, str]":
    """Parse the marker agent's `pairs.json` into `[(x_fqn, y_fqn), ...]`.
    `kind`/`why` are advisory (the mechanical gate decides exact/near) and are
    ignored here. Returns `(pairs, "")` or `(None, error)`."""
    import json
    try:
        data = json.loads(_strip_json_fence(text))
    except Exception as e:  # noqa: BLE001
        return None, f"pairs.json is not valid JSON: {e}"
    if not isinstance(data, list):
        return None, "pairs.json must be a JSON array"
    pairs: list[tuple[str, str]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict) or "x" not in item or "y" not in item:
            return None, f"pair {i} missing 'x'/'y'"
        x, y = item["x"], item["y"]
        if not isinstance(x, str) or not isinstance(y, str):
            return None, f"pair {i} 'x'/'y' must be strings"
        pairs.append((x, y))
    return pairs, ""


def run_llm_dedup(workspace: Path, problem: str, *, apply: bool = False,
                  bridge: bool = True, timeout_sec: int | None = None) -> "dict":
    """v1b-① standalone LLM dedup. Spawns the marker agent via the framework's
    `spawn_llm` (Context.md = `mark_context`, prompt = librarian/dedup.md, JSON
    out = pairs.json) — same proposer pattern as classify — then runs the
    proposed pairs through the mechanical exact-defeq gate (`apply_llm_pairs`,
    rewire-or-revert). DB-free + dispatcher-free: `spawn_llm` takes only paths.
    Returns `apply_llm_pairs`'s dict augmented with `rc`/`error`/`proposed`."""
    from ... import agent
    fail = {"dropped": {}, "near": [], "skipped": [], "proposed": 0}
    pid = agent.new_pipeline_id()
    attempts = agent.attempts_dir_for(workspace, pid)
    (attempts / "Context.md").write_text(
        mark_context(workspace, problem), encoding="utf-8")
    prompt_path = workspace / "Tooling" / "prompts" / "librarian" / "dedup.md"
    problem_dir = workspace.joinpath("Problems", *problem.split("."))
    rc = agent.spawn_llm(
        kind="librarian", prompt_path=prompt_path, problem_dir=problem_dir,
        attempts_dir=attempts, session_id=agent.new_pipeline_id(),
        timeout_sec=timeout_sec)
    if rc != 0:
        return {**fail, "rc": rc, "error": f"marker agent rc={rc}"}
    out = attempts / "pairs.json"
    if not out.exists():
        return {**fail, "rc": rc, "error": "marker wrote no pairs.json"}
    pairs, err = parse_dedup_pairs(out.read_text(encoding="utf-8"))
    if err:
        return {**fail, "rc": rc, "error": err}
    print(f"[dedup-llm] marker proposed {len(pairs)} pair(s)", flush=True)
    res = apply_llm_pairs(workspace, problem, pairs, apply=apply)
    out = {**res, "rc": rc, "error": "", "proposed": len(pairs),
           "bridged": {}, "bridge_failed": []}
    if apply and res["near"] and bridge:          # 3.1b on the near-dups
        br = run_llm_bridge(workspace, problem, res["near"], apply=apply)
        out["bridged"] = br.get("bridged", {})
        out["bridge_failed"] = br.get("failed", [])
    return out


def bridge_context(workspace: Path, problem: str,
                   near_pairs: "list[tuple[str, str]]") -> str:
    """Context for the 3.1b bridger: for each near-dup pair, X's full source
    block (statement + the proof to collapse) and Y's signature/fqn to cite."""
    scope, pool = _load_decls(workspace, problem)
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
        X, Y = by_fqn.get(x), by_fqn.get(y)
        if X is None or Y is None:
            continue
        lines += [f"## pair {i}", f"### x = {X.fqn}  (replace its proof)",
                  "```lean", block(X), "```",
                  f"### y = {Y.fqn}  (cite this)",
                  f"{Y.fqn} :: {' '.join(Y.sig.split())}", ""]
    return "\n".join(lines)


def run_llm_bridge(workspace: Path, problem: str,
                   near_pairs: "list[tuple[str, str]]", *, apply: bool = False
                   ) -> "dict":
    """v1b-②: spawn the bridger (Context = `bridge_context`, prompt =
    librarian/dedup_bridge.md, JSON out = bridges.json), then collapse each
    proposed near-dup's proof via `apply_bridge` (build-gated; revert on fail).
    Returns `{'bridged': {x:y}, 'failed': [(x,y)], 'rc', 'error'}`."""
    import json
    from ... import agent
    scope, pool = _load_decls(workspace, problem)
    by_fqn = {d.fqn: d for d in (*pool, *scope)}
    scope_rels = sorted({d.rel for d in scope})
    fail = {"bridged": {}, "failed": list(near_pairs)}
    pid = agent.new_pipeline_id()
    attempts = agent.attempts_dir_for(workspace, pid)
    (attempts / "Context.md").write_text(
        bridge_context(workspace, problem, near_pairs), encoding="utf-8")
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
        X, Y = by_fqn.get(x), by_fqn.get(y)
        if X is None or Y is None or not isinstance(br, str) or not br.strip():
            continue
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


if __name__ == "__main__":
    import json
    import sys
    ws = Path(".").resolve()
    prob = sys.argv[1] if len(sys.argv) > 1 else ""
    do_apply = "--apply" in sys.argv
    if "--mark" in sys.argv:                      # 3.0 context for the marker
        print(mark_context(ws, prob))
    elif "--llm" in sys.argv:                     # v1b: spawn marker (+bridger)
        res = run_llm_dedup(ws, prob, apply=do_apply,
                            bridge="--no-bridge" not in sys.argv)
        if res.get("error"):
            print(f"[dedup-llm] FAILED: {res['error']}")
        bridged = res.get("bridged", {})
        merged = res.get("merged", set())
        ndrop = len(res["dropped"]) - len(merged)
        print(f"\n=== dedup-llm {'APPLIED' if do_apply else 'DRY'} on {prob}: "
              f"{ndrop} drop(s), {len(merged)} merged, {len(bridged)} bridged, "
              f"{len(res['near'])} near, {len(res['skipped'])} skipped "
              f"(of {res.get('proposed', 0)} proposed) ===")
        for x, y in res["dropped"].items():
            kind = "merge" if x in merged else "drop "
            print(f"  {kind}  {x.rsplit('.', 1)[-1]}  →  cite {y.rsplit('.', 1)[-1]}")
        for x, y in bridged.items():
            print(f"  bridge {x.rsplit('.', 1)[-1]}  →  cite {y.rsplit('.', 1)[-1]}")
        for x, y in res["near"]:
            if x not in bridged:
                print(f"  near   {x.rsplit('.', 1)[-1]}  ~  {y.rsplit('.', 1)[-1]}")
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
