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
        if rc != 0:
            print(f"[dedup] batch_defeq: rc={rc} with no parsed Lean error line "
                  f"— refusing all {len(pairs)} pair(s) (probe env issue); "
                  f"tail: {output[-300:].strip()}", flush=True)
        return [True] * len(pairs) if rc == 0 else [False] * len(pairs)
    in_pair = set()
    for el in error_lines:
        for i, start in enumerate(pair_start_lines):
            end = (pair_start_lines[i + 1] - 1
                   if i + 1 < len(pair_start_lines) else len(lines))
            if start <= el <= end:
                in_pair.add(el)
                break
    if error_lines - in_pair:        # global error (import/env) → cannot judge any
        # NOT a "not defeq" verdict — the probe environment is broken (commonly a
        # stale/missing dependency olean mid-cleanup). Refuse all, but LOUDLY: a
        # silent all-False here masks lost dedups as "near/bridge" (Finding B).
        print(f"[dedup] batch_defeq: GLOBAL probe error (rc={rc}, "
              f"{len(error_lines - in_pair)} error line(s) outside pair blocks) "
              f"— refusing all {len(pairs)} pair(s); likely stale/missing olean. "
              f"tail: {output[-400:].strip()}", flush=True)
        return [False] * len(pairs)
    results = []
    for i, start in enumerate(pair_start_lines):
        end = (pair_start_lines[i + 1] - 1
               if i + 1 < len(pair_start_lines) else len(lines))
        results.append(not any(start <= el <= end for el in error_lines))
    return results


def _lake_check(workspace: Path, content: str, *,
                prefix: str = "_cleanup_probe",
                timeout: int = _BATCH_TIMEOUT_SEC) -> "tuple[bool, str]":
    """Write `content` to a throwaway .lean under .attempts and `lake env lean`
    it (cold; typecheck only, no olean). Returns `(ok, detail)` — ok iff rc==0
    and no lake error line. Shared isolate-typecheck primitive behind
    `_build_decl_isolated` (per-decl probe) and `_build_file_copy_isolated`
    (whole-file copy, §13 (d))."""
    tmp_dir = workspace / ".attempts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_dir / f"{prefix}_{uuid.uuid4().hex}.lean"
    tmp_file.write_text(content, encoding="utf-8")
    try:
        r = subprocess.run(
            ["lake", "env", "lean", str(tmp_file)], cwd=str(workspace),
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout)
        output = r.stdout + r.stderr
        ok = r.returncode == 0 and not _dd._LAKE_ERR_RE.search(output)
        return ok, ("" if ok else output[-2000:])
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e)
    finally:
        try:
            tmp_file.unlink()
        except OSError:
            pass


def _build_decl_isolated(workspace: Path, *, sig: str, proof: str,
                         modules: "list[str]", namespaces: "list[str]",
                         timeout: int = _BATCH_TIMEOUT_SEC
                         ) -> "tuple[bool, str]":
    """Per-decl isolation gate (option-1 inner gate): does
    `theorem _cleanup_probe : <∀-form of sig> := <proof>` typecheck on its own?

    The scratch imports `modules` — the decl's OWN file module (built post-
    migrate, so its same-file siblings + cross-file deps resolve from oleans)
    plus any module the new `proof` cites — and `open`s `namespaces` so bare
    same-namespace references in the proof/sig resolve. This is the cheap inner
    check for a sig-preserving edit (bridge / proof-golf): no whole-file or
    whole-problem rebuild. Returns `(ok, detail)`. Cold `lake env lean` (a warm
    gateway is no faster on a fresh Mathlib file — #108).

    `sig` is kept in BINDER form (`<binders> : <concl>`), NOT ∀-collapsed: a
    real proof references the binders by name, so they must be theorem
    parameters (in scope for the body), not bound under a leading ∀."""
    raw_sig = " ".join(sig.split())
    real_mods = sorted({m for m in modules if m})
    missing = _missing_oleans(workspace, real_mods)                   # O1
    if missing:
        from ...pipeline._lake import lake_build_modules
        try:
            lake_build_modules(workspace, missing)
        except Exception:  # noqa: BLE001 — best-effort pre-flight
            pass
    lines = ["import Mathlib"]
    lines += [f"import {m}" for m in real_mods]
    lines.append("")
    lines += [f"open {ns}" for ns in namespaces if ns]
    lines.append(f"theorem _cleanup_probe {raw_sig} := {proof}")
    content = "\n".join(lines)
    return _lake_check(workspace, content, timeout=timeout)


def _build_file_copy_isolated(workspace: Path, new_text: str, *,
                              extra_modules: "list[str]" = (),
                              timeout: int = _BATCH_TIMEOUT_SEC
                              ) -> "tuple[bool, str]":
    """Isolate-typecheck a WHOLE Library file's proposed new content (§13 (d)
    consumer rewire): `lake env lean` a throwaway copy of `new_text`. The copy
    is NOT registered as its module (no path clash), so this verifies the edit
    without overwriting the real file or producing an olean — the real file's
    olean is rebuilt later (its own (e) / Gate B). `extra_modules` (e.g. a
    survivor's module newly `import`ed by the rewire) are pre-flight built so
    their oleans exist. Returns `(ok, detail)`."""
    missing = _missing_oleans(workspace, [m for m in extra_modules if m])   # O1
    if missing:
        from ...pipeline._lake import lake_build_modules
        try:
            lake_build_modules(workspace, missing)
        except Exception:  # noqa: BLE001 — best-effort pre-flight
            pass
    return _lake_check(workspace, new_text, prefix="_cleanup_filecopy",
                       timeout=timeout)


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


def _code_tokens(text: str) -> "list[str]":
    """Whitespace-split tokens of the CODE regions only (comments stripped via
    `_code_spans`). The basis for the docstring (e) pass's safety gate: a pure
    doc-comment edit leaves this list identical."""
    return " ".join(text[s:e] for s, e in _code_spans(text)).split()


def code_token_invariant(old: str, new: str) -> bool:
    """True iff `old` and `new` have identical CODE content (comments aside) —
    i.e. the edit ONLY touched comments. The whole-file docstring pass's safety
    net (§13 (e), §3 non-code-token diff): an agent that merely adds/fixes doc
    comments leaves every code token untouched; ANY code change → reject (the
    blind-rewrite-corruption guard, #91). Build is the second gate (a malformed
    `/-- -/` still parses-breaks even with code unchanged)."""
    return _code_tokens(old) == _code_tokens(new)


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


def _olean_path(workspace: Path, module: str) -> Path:
    """Where lake writes `module`'s olean (`.lake/build/lib/lean/<A/B/C>.olean`)."""
    return (workspace / ".lake" / "build" / "lib" / "lean"
            / (module.replace(".", "/") + ".olean"))


def _missing_oleans(workspace: Path, modules: "list[str]") -> "list[str]":
    """Modules with no built olean — the only ones a pre-flight must build.
    Post-migrate (in-chain) and post-build (standalone CLI) every cited Library
    module's olean already exists, so the pre-flight `lake_build_modules` (~24s
    of lake graph-check even when nothing rebuilds) is pure overhead → skip it
    (O1). Returns the subset still needing a build; safe because a falsely-kept
    module just pays the (correct) build, and an existing olean is current
    (cited deps are not edited during this file's cleanup)."""
    return sorted({m for m in modules if m
                   and not _olean_path(workspace, m).exists()})


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


def _load_decls(workspace: Path, problem: str,
                scope_index: "list[tuple[str, str]] | None" = None
                ) -> "tuple[list[_Decl], list[_Decl]]":
    """(scope decls for `problem`, domain pool decls). Both theorem/lemma
    with parseable sigs.

    `scope_index`: optional `[(fqn, rel)]` for the scope. In-chain, cleanup
    runs BEFORE bridge writes `INDEX.md`, so the problem's own decls aren't in
    INDEX yet — the caller supplies them from the DB (migrated rows'
    target_name/target_file). None → read scope from INDEX (standalone). The
    pool always comes from INDEX (= other, already-promoted problems)."""
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
        workspace, sig=X.sig, proof=bridge, modules=mods, namespaces=[X.module])
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


def find_thin_wrappers(workspace: Path, problem: str
                       ) -> "list[tuple[str, str, str | None]]":
    """Flag THIN-proof scope decls — one-liners — as dedup/inline suspicions
    (a thin wrapper's proof literally names its twin). Mechanical detector
    behind the standalone `--thin` scan. Returns
    `[(fqn, oneline_proof, cited_lemma_or_None)]`: `cited` = the lemma a
    delegating one-liner hands off to (its likely twin → a dedup pair), None
    for pure automation (`by simp`/`norm_num` — an inline candidate)."""
    scope, _ = _load_decls(workspace, problem)
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
                    scope_index: "list[tuple[str, str]] | None" = None
                    ) -> "dict":
    """3.0→3.1a: run LLM-marked candidate pairs `(x_fqn dups y_fqn)` through
    the mechanical exact-defeq gate. `x` must be a scope decl; `y` any domain
    decl. A pair lands a DROP only when x≡y (defeq), y is the deterministic
    survivor, and x has no cross-problem consumer — then drop x + rewire
    (rewire-or-revert), identical to v1a. Returns
    `{'dropped': {x:y}, 'near': [(x,y)], 'skipped': [(x,y)]}`; `near` =
    marked but not defeq → the 3.1b bridger's input."""
    scope, pool = _load_decls(workspace, problem, scope_index)
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


def bridge_context(workspace: Path, problem: str,
                   near_pairs: "list[tuple[str, str]]",
                   scope_index: "list[tuple[str, str]] | None" = None) -> str:
    """Context for the 3.1b bridger: for each near-dup pair, X's full source
    block (statement + the proof to collapse) and Y's signature/fqn to cite."""
    scope, pool = _load_decls(workspace, problem, scope_index)
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
                   scope_index: "list[tuple[str, str]] | None" = None
                   ) -> "dict":
    """v1b-②: spawn the bridger (Context = `bridge_context`, prompt =
    librarian/dedup_bridge.md, JSON out = bridges.json), then collapse each
    proposed near-dup's proof via `apply_bridge` (build-gated; revert on fail).
    Returns `{'bridged': {x:y}, 'failed': [(x,y)], 'rc', 'error'}`."""
    import json
    from ... import agent
    scope, pool = _load_decls(workspace, problem, scope_index)
    by_fqn = {d.fqn: d for d in (*pool, *scope)}
    scope_rels = sorted({d.rel for d in scope})
    fail = {"bridged": {}, "failed": list(near_pairs)}
    pid = agent.new_pipeline_id()
    attempts = agent.attempts_dir_for(workspace, pid)
    (attempts / "Context.md").write_text(
        bridge_context(workspace, problem, near_pairs, scope_index),
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


def _collect_marked_pairs(workspace: Path, problem: str, *, concurrency: int = 4,
                          scope_index: "list[tuple[str, str]] | None" = None
                          ) -> "tuple[list[tuple[str, str]], list[_Decl], list[_Decl]]":
    """Per-file audit marking (parallel): one agent per Library file emits a
    verdict per decl → uniq (x_fqn, y_fqn) pairs. The shared precursor of both
    the legacy batch gate (`run_file_audit_dedup`) and the staged pipeline
    (`run_staged_cleanup`). Returns (uniq_pairs, scope, pool)."""
    from concurrent.futures import ThreadPoolExecutor
    scope, pool = _load_decls(workspace, problem, scope_index)
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
                    prior_survivors: "set[str]" = frozenset()
                    ) -> "tuple[dict[str, tuple[_Decl, str]], list[tuple[str, str]]]":
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
    scope, pool = _load_decls(workspace, problem, scope_index)
    by_fqn = {d.fqn: d for d in (*pool, *scope)}
    scope_fqns = {d.fqn for d in scope}
    scope_rels = {d.rel for d in scope}
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
        if not is_mathlib and X.rel != Y.rel and _survivor(X.fqn, Y.fqn) != Y.fqn:
            skipped.append((X.fqn, Y.fqn))             # cross-file: keep canonical
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
                     scope_index: "list[tuple[str, str]] | None" = None
                     ) -> "dict[str, str]":
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
        bridge_context(workspace, problem, pairs, scope_index), encoding="utf-8")
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
        t, n1 = replace_token(text, xfqn, Y.fqn)
        t, n2 = replace_token(t, xname, Y.fqn)
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
            iso = bool(br) and d.fqn != Y.fqn and Y.fqn not in drops and \
                _build_decl_isolated(
                    workspace, sig=d.sig, proof=br, namespaces=[d.module],
                    modules=[d.module] + ([Y.module] if Y.module else []))[0]
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
                       scope_index: "list[tuple[str, str]] | None" = None
                       ) -> "dict":
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
        workspace, problem, concurrency=concurrency, scope_index=scope_index)
    _t1 = _c()
    plan, skipped = _classify_pairs(workspace, problem, uniq,
                                    scope_index=scope_index)
    _t2 = _c()
    bridge_pairs = [(x, Y.fqn) for x, (Y, k) in plan.items() if k == "bridge"]
    bridges = (_propose_bridges(workspace, problem, bridge_pairs,
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
        _update_index(workspace, set(dropped))     # bridged keep their statement
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
# P2a — docstring polish (§13 (e) file-cleanup, whole-file)
#
# After a file's per-decl passes (dedup), one agent rewrites the WHOLE file
# adding/fixing decl docstrings + a module note. Two gates: code-token
# invariance (`code_token_invariant` — only comments may change, the #91
# blind-rewrite guard) then a whole-file isolate build (`_build_file_copy_
# isolated` — a malformed `/-- -/` still parse-breaks with code unchanged).
# Build failure feeds the lake error back and re-spawns up to a threshold;
# exhaustion keeps the original file (decline = safe no-op on the green
# baseline). Comment-only, so it never changes a signature → no consumer
# rewrite (no step (d)).
# ---------------------------------------------------------------------

_DOCSTRING_PROMPT = "docstring.md"
_DOCSTRING_MAX_RETRIES = 2


def _docstring_context(workspace: Path, problem: str, rel: str,
                       decl_names: "list[str]", prev_error: str = "") -> str:
    """Per-file context for the docstring agent: the module, its declarations,
    the verbatim current file, and (on retry) the previous build error to fix."""
    try:
        body = (workspace / rel).read_text(encoding="utf-8")
    except OSError:
        body = ""
    lines = [
        f"# Docstring polish — {problem} — `{rel}`", "",
        f"Module: `{_mod_of_rel(rel)}`.",
        f"Declarations: {', '.join(decl_names) or '(none)'}", "",
        "## Current file (reproduce ALL code verbatim — only doc comments "
        "may change)", "", "```lean", body.rstrip(), "```", "",
    ]
    if prev_error:
        lines += ["## Your previous attempt failed — fix and retry", "",
                  "```", prev_error[-1500:], "```", ""]
    return "\n".join(lines) + "\n"


def file_cleanup_docstrings(workspace: Path, problem: str, target_file: str,
                            decl_names: "list[str]", *,
                            max_retries: int = _DOCSTRING_MAX_RETRIES) -> bool:
    """§13 (e) docstring pass for ONE file. Spawn → code-token-invariance gate
    → whole-file isolate build → on fail feed the error & re-spawn (≤
    max_retries) → exhaustion keeps the original. Writes `target_file` in place
    on success. Returns whether the file changed. No-op (False) if the prompt
    is absent (lets the chain enable P2 before the prompt is finalised)."""
    from ... import agent
    prompt_path = workspace / "Tooling" / "prompts" / "librarian" / _DOCSTRING_PROMPT
    if not prompt_path.exists():
        return False
    try:
        original = (workspace / target_file).read_text(encoding="utf-8")
    except OSError:
        return False
    problem_dir = workspace.joinpath("Problems", *problem.split("."))
    leaf = target_file.split("/")[-1]
    prev_error = ""
    for attempt in range(max_retries + 1):
        attempts = agent.attempts_dir_for(workspace, agent.new_pipeline_id())
        (attempts / "Context.md").write_text(
            _docstring_context(workspace, problem, target_file, decl_names,
                               prev_error), encoding="utf-8")
        rc = agent.spawn_llm(kind="librarian", prompt_path=prompt_path,
                             problem_dir=problem_dir, attempts_dir=attempts,
                             session_id=agent.new_pipeline_id())
        out = attempts / "annotated.lean"
        if rc != 0 or not out.exists():
            prev_error = "no annotated.lean was produced"
            continue
        new_text = out.read_text(encoding="utf-8")
        if new_text.strip() == original.strip():
            return False                          # nothing to add — clean no-op
        if not code_token_invariant(original, new_text):
            prev_error = ("you changed CODE — only doc comments (`/-- -/`, "
                          "`--`, `/-! -/`) may change; reproduce every "
                          "declaration's code verbatim")
            continue
        ok, detail = _build_file_copy_isolated(workspace, new_text)
        if ok:
            (workspace / target_file).write_text(new_text, encoding="utf-8")
            print(f"[staged] docstring `{leaf}` — polished "
                  f"(try {attempt + 1})", flush=True)
            return True
        prev_error = detail
    print(f"[staged] docstring `{leaf}` — kept original "
          f"(no green annotation in {max_retries + 1} tries)", flush=True)
    return False


# ---------------------------------------------------------------------
# P2b — proof simplification (§13 (c) decl-cleanup, marked-only per-decl)
#
# Whole-proof rewrite is too expensive to attempt on every decl, so a per-file
# marker (one agent) first picks which proofs are worth shortening; only those
# pay the per-decl cost. Each marked survivor is then simplified in isolation:
# spawn → `_build_decl_isolated` (sig-preserving probe, reused from bridge) → on
# build failure feed the lake error & re-spawn up to a threshold → exhaustion
# (or a decline / no-change) keeps the original proof (safe no-op on the green
# baseline). Sig-preserving → no consumer rewrite. Runs on POST-dedup text, and
# skips dropped (gone) / bridged (already one-liners) decls (precedence
# drop > bridge > simplify).
# ---------------------------------------------------------------------

_SIMPLIFY_MARK_PROMPT = "cleanup_mark.md"
_SIMPLIFY_PROMPT = "decl_simplify.md"
_SIMPLIFY_MAX_RETRIES = 2


def _parse_simplify_marks(text: str) -> "set[str]":
    """Parse the simplify marker's JSON array → a set of decl (leaf) names.
    Accepts `["a","b"]` or `[{"decl":"a"}, …]`; ignores malformed entries."""
    import json
    try:
        data = json.loads(_strip_json_fence(text))
    except Exception:  # noqa: BLE001
        return set()
    out: set[str] = set()
    if isinstance(data, list):
        for it in data:
            if isinstance(it, str) and it.strip():
                out.add(it.strip())
            elif isinstance(it, dict) and isinstance(it.get("decl"), str):
                out.add(it["decl"].strip())
    return out


def _simplify_mark_context(workspace: Path, problem: str, rel: str,
                           decl_names: "list[str]") -> str:
    try:
        body = (workspace / rel).read_text(encoding="utf-8")
    except OSError:
        body = ""
    return "\n".join([
        f"# Proof-simplification triage — {problem} — `{rel}`", "",
        f"Module: `{_mod_of_rel(rel)}`.",
        f"Candidate declarations: {', '.join(decl_names) or '(none)'}", "",
        "## Current file", "", "```lean", body.rstrip(), "```", "",
    ]) + "\n"


def _simplify_decl_context(workspace: Path, problem: str, rel: str, name: str,
                           sig: str, proof: str, prev_error: str = "") -> str:
    lines = [
        f"# Simplify one proof — {problem} — `{name}`", "",
        f"Module: `{_mod_of_rel(rel)}` (its declarations + imports are in scope).",
        "", "## Statement (keep verbatim)", "", "```lean", sig.strip(), "```",
        "", "## Current proof (everything after `:=`)", "",
        "```lean", proof.strip(), "```", "",
    ]
    if prev_error:
        lines += ["## Your previous attempt failed to build — fix and retry", "",
                  "```", prev_error[-1500:], "```", ""]
    return "\n".join(lines) + "\n"


def _mark_simplify_file(workspace: Path, problem: str, rel: str,
                        decl_names: "list[str]", problem_dir: Path) -> "set[str]":
    """Spawn the simplify marker over one file; return the subset of `decl_names`
    worth proof-simplifying. No-op (empty) if the prompt is absent."""
    from ... import agent
    prompt_path = (workspace / "Tooling" / "prompts" / "librarian"
                   / _SIMPLIFY_MARK_PROMPT)
    if not prompt_path.exists() or not decl_names:
        return set()
    attempts = agent.attempts_dir_for(workspace, agent.new_pipeline_id())
    (attempts / "Context.md").write_text(
        _simplify_mark_context(workspace, problem, rel, decl_names),
        encoding="utf-8")
    rc = agent.spawn_llm(kind="librarian", prompt_path=prompt_path,
                         problem_dir=problem_dir, attempts_dir=attempts,
                         session_id=agent.new_pipeline_id())
    out = attempts / "simplify.json"
    if rc != 0 or not out.exists():
        return set()
    return _parse_simplify_marks(out.read_text(encoding="utf-8")) & set(decl_names)


def _propose_simplify(workspace: Path, problem: str, rel: str, name: str,
                      sig: str, proof: str, problem_dir: Path,
                      prev_error: str = "") -> "str | None":
    """One simplify spawn for decl `name`; return the proposed new proof body
    (text after `:=`), or None on decline / failure."""
    from ... import agent
    prompt_path = (workspace / "Tooling" / "prompts" / "librarian"
                   / _SIMPLIFY_PROMPT)
    if not prompt_path.exists():
        return None
    attempts = agent.attempts_dir_for(workspace, agent.new_pipeline_id())
    (attempts / "Context.md").write_text(
        _simplify_decl_context(workspace, problem, rel, name, sig, proof,
                               prev_error), encoding="utf-8")
    rc = agent.spawn_llm(kind="librarian", prompt_path=prompt_path,
                         problem_dir=problem_dir, attempts_dir=attempts,
                         session_id=agent.new_pipeline_id())
    out = attempts / "simplified.txt"
    if rc != 0 or not out.exists():
        return None
    new_proof = out.read_text(encoding="utf-8").strip()
    return new_proof or None


def decl_cleanup_simplify_file(workspace: Path, problem: str, target_file: str,
                               decls: "list[_Decl]", marked: "set[str]", *,
                               max_retries: int = _SIMPLIFY_MAX_RETRIES) -> int:
    """§13 (c) per-decl proof simplification for ONE file. For each `marked`
    survivor (source order): spawn → `_build_decl_isolated` (sig-preserving) →
    on fail feed the error & retry (≤ max_retries) → decline / no-change /
    exhaustion keeps the original proof. Writes `target_file` in place if any
    proof changed. Returns the count simplified. No-op (0) if the prompt is
    absent or nothing is marked."""
    if not marked:
        return 0
    problem_dir = workspace.joinpath("Problems", *problem.split("."))
    try:
        text = (workspace / target_file).read_text(encoding="utf-8")
    except OSError:
        return 0
    n = 0
    for d in decls:                                # source order, marked only
        if d.name not in marked:
            continue
        cur = decl_proof_body(text, d.name)
        if cur is None:
            continue
        prev_error = ""
        for _attempt in range(max_retries + 1):
            new_proof = _propose_simplify(
                workspace, problem, target_file, d.name, d.sig, cur,
                problem_dir, prev_error)
            if not new_proof or new_proof.strip() == cur.strip():
                break                              # decline / no change → keep
            ok, detail = _build_decl_isolated(
                workspace, sig=d.sig, proof=new_proof,
                modules=[d.module], namespaces=[d.module])
            if ok:
                nt, replaced = replace_proof(text, d.name, new_proof)
                if replaced:
                    text = nt
                    n += 1
                    print(f"[staged] simplified {d.name}", flush=True)
                break
            prev_error = detail
    if n:
        (workspace / target_file).write_text(text, encoding="utf-8")
    return n


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

_VARIABLE_PROMPT = "variable_extract.md"
_VARIABLE_OUTPUT = "refactored.lean"
_VARIABLE_MAX_RETRIES = 2


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


def _norm_type(s: str) -> str:
    """Canonical form for comparing `#check` types: collapse whitespace and
    erase auto universe names (`u_1`→`u`) so a binder reorder that only renames
    universes isn't a false mismatch."""
    return " ".join(re.sub(r"\bu_\d+\b", "u", s).split())


def _typecheck_capturing_types(workspace: Path, file_text: str,
                               fqns: "list[str]", *,
                               timeout: int = _BATCH_TIMEOUT_SEC
                               ) -> "tuple[bool, str, dict[str, str]]":
    """Isolate-build `file_text` with `#check @<fqn>` appended for each decl
    (`lean --json`), returning `(ok, detail, {fqn: normalized_type})`. One build
    serves as both the proof gate (an error → ok False) and the signature
    snapshot. `@` forces all args explicit so implicit/explicit flips show up."""
    import json
    checks = "\n".join(f"#check @{f}" for f in fqns)
    content = file_text.rstrip() + "\n\n" + checks + "\n"
    tmp_dir = workspace / ".attempts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_dir / f"_cleanup_vcheck_{uuid.uuid4().hex}.lean"
    tmp_file.write_text(content, encoding="utf-8")
    try:
        r = subprocess.run(
            ["lake", "env", "lean", "--json", str(tmp_file)], cwd=str(workspace),
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e), {}
    finally:
        try:
            tmp_file.unlink()
        except OSError:
            pass
    ok, errs, types = r.returncode == 0, [], {}
    for line in (r.stdout + "\n" + r.stderr).splitlines():
        s = line.strip()
        if not (s.startswith("{") and s.endswith("}")):
            continue
        try:
            msg = json.loads(s)
        except Exception:  # noqa: BLE001
            continue
        sev, data = msg.get("severity"), msg.get("data", "")
        if sev == "error":
            ok = False
            errs.append(data)
        elif sev == "information":
            for f in fqns:
                if data.startswith(f"@{f} :"):
                    types[f] = _norm_type(data[len(f"@{f} :"):])
                    break
    if ok and len(types) != len(fqns):
        return False, "could not read #check output for every declaration", types
    detail = "" if ok else ("\n\n".join(errs)[-2000:] or (r.stdout + r.stderr)[-2000:])
    return ok, detail, types


def _variable_context(workspace: Path, problem: str, rel: str,
                      decl_names: "list[str]", shared: "list[str]",
                      prev_error: str = "") -> str:
    """Per-file context for the variable-extraction agent: module, declarations,
    the mechanically-detected shared binders (hoist hints), the verbatim file,
    and (on retry) the previous failure to fix."""
    try:
        body = (workspace / rel).read_text(encoding="utf-8")
    except OSError:
        body = ""
    lines = [
        f"# Variable extraction — {problem} — `{rel}`", "",
        f"Module: `{_mod_of_rel(rel)}`.",
        f"Declarations: {', '.join(decl_names) or '(none)'}", "",
        "Binders detected as shared across this file (candidates to hoist into a "
        "`variable` block):", "",
    ]
    lines += ([f"- `{a}`" for a in shared]
              if shared else ["- (none detected — focus on un-∀)"])
    lines += ["", "## Current file", "", "```lean", body.rstrip(), "```", ""]
    if prev_error:
        lines += ["## Your previous attempt failed — fix and retry", "",
                  "```", prev_error[-1500:], "```", ""]
    return "\n".join(lines) + "\n"


def file_cleanup_variables(workspace: Path, problem: str, target_file: str,
                           decls_in_file: "list[_Decl]", *,
                           max_retries: int = _VARIABLE_MAX_RETRIES) -> bool:
    """§13 (e) variable-extraction pass for ONE file. Pre-filter (skip if nothing
    to un-∀ and no shared binders) → snapshot decl types → spawn → #check gate
    (proof builds AND every decl's elaborated type unchanged) → on fail feed the
    error & re-spawn (≤ max_retries) → exhaustion keeps the original. Writes
    `target_file` in place on success. Returns whether the file changed. No-op
    (False) if the prompt is absent, nothing to do, or the snapshot can't be
    read (don't risk an unverifiable edit)."""
    from ... import agent
    prompt_path = workspace / "Tooling" / "prompts" / "librarian" / _VARIABLE_PROMPT
    if not prompt_path.exists() or not decls_in_file:
        return False
    leaf = target_file.split("/")[-1]
    shared = _shared_binders(decls_in_file)
    if not shared and not any(_is_prenex(d.sig) for d in decls_in_file):
        return False                          # already idiomatic, nothing shared
    try:
        original = (workspace / target_file).read_text(encoding="utf-8")
    except OSError:
        return False
    fqns = [d.fqn for d in decls_in_file]
    ok0, _d0, base_types = _typecheck_capturing_types(workspace, original, fqns)
    if not ok0:
        print(f"[staged] variables `{leaf}` — skip (no type snapshot)", flush=True)
        return False
    decl_names = [d.name for d in decls_in_file]
    problem_dir = workspace.joinpath("Problems", *problem.split("."))
    prev_error = ""
    for attempt in range(max_retries + 1):
        attempts = agent.attempts_dir_for(workspace, agent.new_pipeline_id())
        (attempts / "Context.md").write_text(
            _variable_context(workspace, problem, target_file, decl_names,
                              shared, prev_error), encoding="utf-8")
        rc = agent.spawn_llm(kind="librarian", prompt_path=prompt_path,
                             problem_dir=problem_dir, attempts_dir=attempts,
                             session_id=agent.new_pipeline_id())
        out = attempts / _VARIABLE_OUTPUT
        if rc != 0 or not out.exists():
            prev_error = f"no {_VARIABLE_OUTPUT} was produced"
            continue
        new_text = out.read_text(encoding="utf-8")
        if new_text.strip() == original.strip():
            return False                      # already idiomatic — clean no-op
        ok, detail, new_types = _typecheck_capturing_types(
            workspace, new_text, fqns)
        if not ok:
            prev_error = detail
            continue
        changed = [f for f in fqns if base_types.get(f) != new_types.get(f)]
        if changed:
            prev_error = ("the elaborated type changed for: "
                          + ", ".join(f.rsplit(".", 1)[-1] for f in changed)
                          + " — restructure the spelling, never the type")
            continue
        (workspace / target_file).write_text(new_text, encoding="utf-8")
        print(f"[staged] variables `{leaf}` — extracted (try {attempt + 1})",
              flush=True)
        return True
    print(f"[staged] variables `{leaf}` — kept original "
          f"(no green refactor in {max_retries + 1} tries)", flush=True)
    return False


def run_staged_cleanup_file(workspace: Path, problem: str, target_file: str, *,
                            scope_index: "list[tuple[str, str]] | None" = None,
                            prior_renames: "dict[str, str] | None" = None,
                            apply: bool = True, bridge: bool = True,
                            docstring: bool = False,
                            variables: bool = False,
                            simplify: bool = False) -> "dict":
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
    scope, pool = _load_decls(workspace, problem, scope_index)
    by_fqn = {d.fqn: d for d in (*pool, *scope)}
    decls_in_file = [d for d in scope if d.rel == target_file]
    empty = {"dropped": {}, "merged": set(), "bridged": {}, "near": [], "failed": []}
    if not decls_in_file:
        return empty
    scope_by_leaf = {d.name: d for d in scope}
    all_by_leaf = {d.name: d for d in (*pool, *scope)}
    prompt_path = workspace / "Tooling" / "prompts" / "librarian" / "dedup_audit.md"
    problem_dir = workspace.joinpath("Problems", *problem.split("."))
    pairs, log = _audit_one_file(workspace, problem, target_file, scope, pool,
                                 scope_by_leaf, all_by_leaf, prompt_path, problem_dir)
    print(log, flush=True)
    plan, _skipped = _classify_pairs(
        workspace, problem, sorted(set(pairs)), scope_index=scope_index,
        prior_dropped=set(prior_renames),
        prior_survivors=set(prior_renames.values()))
    if not apply:
        return {**empty,
                "dropped": {x: Y.fqn for x, (Y, k) in plan.items() if k == "drop"},
                "near": [(x, Y.fqn) for x, (Y, k) in plan.items() if k == "bridge"]}
    bridge_pairs = [(x, Y.fqn) for x, (Y, k) in plan.items() if k == "bridge"]
    bridges = (_propose_bridges(workspace, problem, bridge_pairs,
                                scope_index=scope_index)
               if (bridge and bridge_pairs) else {})
    rename_map = [(_decl_from_fqn(xf, by_fqn), _decl_from_fqn(yf, by_fqn))
                  for xf, yf in prior_renames.items()]
    r = _cleanup_one_file(workspace, target_file, decls_in_file, plan, bridges,
                          rename_map, _Splicer(workspace))
    for xf, Yd in r["drops"].items():
        tag = "merged" if xf in r["merged"] else "dropped"
        print(f"[staged] {tag} {xf.rsplit('.', 1)[-1]} → cite {Yd.name}", flush=True)
    for xf, Yd in r["bridged"]:
        print(f"[staged] bridged {xf.rsplit('.', 1)[-1]} → cite {Yd.name}", flush=True)
    # Survivors of this file's dedup pass: not dropped, not bridged (bridges are
    # already one-liners). The (c) simplify + (e) docstring passes run on these.
    bridged_fqns = {x for x, _ in r["bridged"]}
    survivor_decls = [d for d in decls_in_file
                      if d.fqn not in r["drops"] and d.fqn not in bridged_fqns]
    # (c) decl-cleanup — per-decl proof simplification (marked-only). Sig-
    # preserving → no consumer rewrite. Runs BEFORE docstrings (§13 order).
    n_simplified = 0
    if simplify and survivor_decls:
        marked = _mark_simplify_file(
            workspace, problem, target_file,
            [d.name for d in survivor_decls],
            workspace.joinpath("Problems", *problem.split(".")))
        n_simplified = decl_cleanup_simplify_file(
            workspace, problem, target_file, survivor_decls, marked)
    # (e) variable extraction — un-∀ + hoist file-wide shared binders. Type-
    # preserving (call-site-invariant), enforced by the #check gate. Runs BEFORE
    # docstrings (structure first, then comments → no re-touch).
    variabled = False
    if variables and survivor_decls:
        variabled = file_cleanup_variables(
            workspace, problem, target_file, survivor_decls)
    # (e) file-cleanup — docstring polish on the (now refactored) file. Comment-
    # only → no signature change. Own gates + retry; failure keeps the file.
    docstringed = False
    if docstring:
        docstringed = file_cleanup_docstrings(
            workspace, problem, target_file, [d.name for d in survivor_decls])
    return {"dropped": {x: Yd.fqn for x, Yd in r["drops"].items()},
            "merged": set(r["merged"]),
            "bridged": {x: Yd.fqn for x, Yd in r["bridged"]},
            "near": r["near"], "failed": r["failed"],
            "simplified": n_simplified, "variabled": variabled,
            "docstringed": docstringed}


def run_file_audit_dedup(workspace: Path, problem: str, *, apply: bool = False,
                         bridge: bool = True, concurrency: int = 4,
                         scope_index: "list[tuple[str, str]] | None" = None
                         ) -> "dict":
    """Legacy batch gate (pre-§13): per-file audit marking → batch mechanical
    gate (`apply_llm_pairs` whole-problem rebuild + batch bridger). Kept for the
    standalone `--audit` CLI; the chain uses `run_staged_cleanup`."""
    uniq, _scope, _pool = _collect_marked_pairs(
        workspace, problem, concurrency=concurrency, scope_index=scope_index)
    res = apply_llm_pairs(workspace, problem, uniq, apply=apply,
                          scope_index=scope_index)
    result = {**res, "proposed": len(uniq), "bridged": {}, "bridge_failed": []}
    if apply and res["near"] and bridge:
        br = run_llm_bridge(workspace, problem, res["near"], apply=apply,
                            scope_index=scope_index)
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
