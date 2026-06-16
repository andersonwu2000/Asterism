"""Shared low-level helpers for the per-file Library cleanup stages.

Extracted verbatim from `dedup.py` so the cleanup stages (simplify /
mechanical / polish / decide / audit) and the dedup core can share one
implementation without an import cycle: this module imports NOTHING from
`dedup.py`. Stage modules do `from . import _common as C` and call
through `C.fn(...)` — one canonical monkeypatch point per helper.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from ... import lake_probe as _lp


_BATCH_TIMEOUT_SEC = 240


class _Decl(NamedTuple):
    fqn: str
    rel: str
    module: str
    name: str
    sig: str
    binders: int
    concl_tokens: "frozenset[str]"


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
    r"""Replace whole-token occurrences of `old` with `new`, in CODE regions
    only. `old` may be a bare name (`col_sum_collapse`) or a dotted FQN
    (`Library.X.col_sum_collapse`). Boundaries treat `[A-Za-z0-9_'.]` as
    identifier chars, so:
      - LEADING boundary excludes `[\w'.]`: a bare `old` does not match
        `A.old` (an FQN tail belongs to the qualified pass) nor `xold`;
      - TRAILING boundary excludes `[\w']` but ALLOWS a `.`:
        `old.contDiffOn` is dot-notation PROJECTION on the very decl being
        renamed — it must rewrite, since the old name ceases to exist and a
        left-behind `old.…` is a guaranteed dangle (stokes bdry_manifold
        2026-06-11: `smooth_face_proj.contDiffOn` survived the deferred
        rename and broke the bridge build). Likewise an FQN followed by
        `.comp` rewrites.
    Returns `(new_text, n_replacements)`.
    """
    pat = re.compile(r"(?<![\w'.])" + re.escape(old) + r"(?![\w'])")
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


def _strip_json_fence(text: str) -> str:
    """Drop a leading ```json / trailing ``` fence if the agent wrapped its
    array (the classify runner tolerates the same — `_load_json`)."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[A-Za-z0-9]*\n", "", t)
        t = re.sub(r"\n?```$", "", t.strip())
    return t.strip()


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


def _lake_check(workspace: Path, content: str, *,
                prefix: str = "_cleanup_probe",
                timeout: int = _BATCH_TIMEOUT_SEC) -> "tuple[bool, str]":
    """Write `content` to a throwaway .lean under .attempts and `lake env lean`
    it (cold; typecheck only, no olean). Returns `(ok, detail)` — ok iff rc==0
    and no lake error line. Shared isolate-typecheck primitive behind
    `_build_decl_isolated` (per-decl probe) and `_build_file_copy_isolated`
    (whole-file copy, §13 (d))."""
    run = _lp.run_lean_source(workspace, content, prefix=prefix, timeout=timeout)
    return run.ok, ("" if run.ok else run.output[-2000:])


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
        from ....pipeline._lake import lake_build_modules
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
        from ....pipeline._lake import lake_build_modules
        try:
            lake_build_modules(workspace, missing)
        except Exception:  # noqa: BLE001 — best-effort pre-flight
            pass
    return _lake_check(workspace, new_text, prefix="_cleanup_filecopy",
                       timeout=timeout)


_DECL_NAME_RE = re.compile(
    r"(?m)^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
    r"(?:private[ \t]+|protected[ \t]+|noncomputable[ \t]+|scoped[ \t]+)*"
    r"(?:theorem|lemma|def)[ \t]+([A-Za-z_][\w'.]*)")


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


def _norm_type(s: str) -> str:
    """Canonical form for comparing `#check` types: collapse whitespace and
    erase auto universe names (`u_1`→`u`) so a binder reorder that only renames
    universes isn't a false mismatch."""
    return " ".join(re.sub(r"\bu_\d+\b", "u", s).split())


def _parse_check_output(output: str, fqns: "list[str]"
                        ) -> "tuple[dict[str, str], list[str]]":
    """Parse `lean --json` output into `({fqn: normalized_type}, [error_data])`.
    `#check @foo` prints `@foo : T`, but Lean drops the `@` when foo has no
    implicit args to expose (`foo : T`) and annotates universes when foo is
    universe-polymorphic (`@foo.{u} : T`) — match all three. The `: ` anchor
    keeps a prefix name (`foo`) from matching a longer one (`foo_bar`)."""
    import json
    types: "dict[str, str]" = {}
    errs: "list[str]" = []
    for line in output.splitlines():
        s = line.strip()
        if not (s.startswith("{") and s.endswith("}")):
            continue
        try:
            msg = json.loads(s)
        except Exception:  # noqa: BLE001
            continue
        sev, data = msg.get("severity"), msg.get("data", "")
        if sev == "error":
            errs.append(data)
        elif sev == "information":
            d = data[1:] if data.startswith("@") else data
            for f in fqns:
                if f in types:
                    continue
                m = re.match(re.escape(f) + r"(?:\.\{[^}]*\})?\s*:\s*(.*)",
                             d, re.S)
                if m:
                    types[f] = _norm_type(m.group(1))
                    break
    return types, errs


def nominal_ctor_suffixes(text: str, leaf: str) -> "list[str]":
    r"""Constructor name(s) of nominal declaration `leaf` in `text`:
    `['mk']` (or the custom `name ::`) for a structure/class, the `| ctor`
    list for an inductive, `[]` when `leaf` is not a nominal decl here.

    Why: the type gate #checks `@Foo`, which for a nominal kind is only the
    SIGNATURE — a whole-file rewriter (polish/audit) could alter a FIELD's
    type and the gate would stay green. The constructor's type strings every
    field type together, so snapshotting `@Foo.mk` (or each inductive ctor)
    extends the gate to fields (desk-check 2026-06-12, first nominal decl
    through cleanup = stokes_integral OrientedManifold)."""
    m = re.search(
        r"(?m)^[ 	]*(?:@\[[^\]]*\][ 	]*)*"
        r"(?:noncomputable[ 	]+|private[ 	]+|protected[ 	]+)*"
        r"(structure|class|inductive)[ 	]+" + re.escape(leaf) + r"\b", text)
    if not m:
        return []
    rest = text[m.start():]
    nxt = re.search(
        r"(?m)^(?:@\[[^\]]*\]\s*)*"
        r"(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
        r"(?:def|abbrev|theorem|lemma|structure|class|inductive|instance)"
        r"\s+[A-Za-z_]"
        r"|^variable\b|^section\b|^end\b", rest[1:])
    span = rest[:nxt.start() + 1] if nxt else rest
    if m.group(1) == "inductive":
        return re.findall(r"(?m)^\s*\|\s*([A-Za-z_][\w']*)", span)
    mm = re.search(r"(?m)^\s*([A-Za-z_][\w']*)\s*::", span)
    return [mm.group(1) if mm else "mk"]


def _typecheck_capturing_types(workspace: Path, file_text: str,
                               fqns: "list[str]", *,
                               timeout: int = _BATCH_TIMEOUT_SEC
                               ) -> "tuple[bool, str, dict[str, str]]":
    """Isolate-build `file_text` with `#check @<fqn>` appended for each decl
    (`lean --json`), returning `(ok, detail, {fqn: normalized_type})`. One build
    serves as both the proof gate (an error → ok False) and the signature
    snapshot. `@` forces all args explicit so implicit/explicit flips show up."""
    missing = _missing_oleans(workspace, re.findall(    # O1: imported sibling
        r"^\s*import\s+(Library\.[\w.]+)", file_text, re.M))   # oleans must exist
    if missing:
        from ....pipeline._lake import lake_build_modules
        try:
            lake_build_modules(workspace, missing)
        except Exception:  # noqa: BLE001 — best-effort pre-flight
            pass
    checks = "\n".join(f"#check @{f}" for f in fqns)
    content = file_text.rstrip() + "\n\n" + checks + "\n"
    run = _lp.run_lean_source(workspace, content, prefix="_cleanup_vcheck",
                              json=True, timeout=timeout)
    if run.infra:
        return False, run.output, {}
    types, errs = _parse_check_output(run.output, fqns)
    ok = run.returncode == 0 and not errs
    if ok and len(types) != len(fqns):
        return False, "could not read #check output for every declaration", types
    detail = "" if ok else ("\n\n".join(errs)[-2000:] or run.output[-2000:])
    return ok, detail, types


def _build_with_output(workspace: Path, content: str, *, prefix: str,
                       timeout: int = _BATCH_TIMEOUT_SEC) -> "tuple[bool, str]":
    """Like `_lake_check` but ALWAYS returns the full build output (stdout+stderr),
    even on success — needed to read linter WARNINGS (rc==0), which `_lake_check`
    discards. `ok` iff rc==0 and no lake error line."""
    run = _lp.run_lean_source(workspace, content, prefix=prefix, timeout=timeout)
    return run.ok, run.output


_WARN_LINE_RE = re.compile(r"\bwarning:[^\n]*")


def _all_warnings(build_output: str) -> "list[str]":
    """Every distinct `warning:` line in a build's full output — the Mathlib-PR
    zero-warning bar (deprecated, unused variable, linter.style, dupNamespace,
    unnecessary, longFile, …). Broader than polish's type-preserving subset
    (`_polish_warnings`, which is only the warnings polish itself can clear): the
    final per-file cleanup gate and the audit reviewer drive the file to ZERO of
    these. `deprecated` in particular is core-Lean (always on) yet was missed by
    the curated subset, so deprecated lemmas (EuclideanSpace.single_apply →
    PiLp.single_apply) shipped silently."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _WARN_LINE_RE.finditer(build_output):
        w = m.group(0).strip()[:200]
        if w and w not in seen:
            seen.add(w)
            out.append(w)
    return out


_VAR_RE = re.compile(r"variable\b")
_SCOPE_RE = re.compile(r"(section|namespace|end)\b")


def _collapse_redundant_variable_blocks(text: str) -> str:
    """Drop a `variable` block that is byte-identical to the immediately
    preceding one (only blank lines between, no `section`/`namespace`/`end`
    in between, so it is the same scope) — a build-harmless no-op re-declaration
    that the per-decl migrate assembly replays (each Defs slice re-emits its
    in-scope variables; StokesIntegralDefs:24/29 shipped two identical blocks).
    Conservative on purpose: only adjacent identical blocks at one scope depth
    collapse, so a block legitimately re-opened after an `end` is never removed.
    Runs on the FINAL file regardless of migrate path (the existing dedup in
    `_mechanical_migrate_file` only covered the mechanical chunk path)."""
    lines = text.splitlines()
    out: list[str] = []
    prev_block: "str | None" = None
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if _VAR_RE.match(s):
            j = i + 1
            while j < n and lines[j][:1] in (" ", "\t") and lines[j].strip():
                j += 1
            block = "\n".join(lines[i:j])
            if block == prev_block:                 # redundant re-declaration
                while out and out[-1].strip() == "":
                    out.pop()                        # collapse separating blanks
                out.append("")
                i = j
                continue
            out.extend(lines[i:j])
            prev_block = block
            i = j
            continue
        if s == "":
            out.append(lines[i]); i += 1
            continue
        # any non-blank, non-variable line breaks adjacency; a scope keyword
        # additionally means a later identical block is a real re-open.
        prev_block = None
        out.append(lines[i]); i += 1
    result = "\n".join(out)
    if text.endswith("\n") and not result.endswith("\n"):
        result += "\n"                              # splitlines() drops it
    return result


def _inject_linter(text: str, *options: str) -> str:
    """Return `text` with `set_option <opt> true` injected after the import block
    (file-level — these linters don't take `… in <command>`). Used to force a
    default-OFF linter on for a detection build."""
    lines = text.splitlines(keepends=True)
    k = max((i + 1 for i, l in enumerate(lines)
             if l.lstrip().startswith("import ")), default=0)
    inj = "".join(f"set_option {o} true\n" for o in options)
    return "".join(lines[:k]) + inj + "".join(lines[k:])


# The project's mathlib-PR lint bar (lakefile.lean `leanOptions`). `lake env
# lean` on a throwaway file does NOT inherit the package leanOptions, so the
# cleanup detection/gate builds must force these ON themselves — otherwise they
# miss the whole mathlib style set (longFile, longLine, cdot, docString,
# multiGoal, …) and only catch default-on lints (deprecated, core unused). The
# file imports Mathlib, so the linter definitions are in scope for set_option.
_MATHLIB_LINT_OPTS = ("linter.mathlibStandardSet", "linter.deprecated")


def _build_for_warnings(workspace: Path, content: str, *, prefix: str,
                        timeout: int = _BATCH_TIMEOUT_SEC) -> "tuple[bool, str]":
    """Like `_build_with_output` but with the mathlib standard linter set forced
    on, so the build surfaces the full mathlib-PR warning set. Returns
    (ok, full_output)."""
    return _build_with_output(
        workspace, _inject_linter(content, *_MATHLIB_LINT_OPTS),
        prefix=prefix, timeout=timeout)


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_']*$")


def _coerce_renames(data) -> "dict[str, str]":
    """Coerce a JSON value into {old_leaf: new_leaf}. Accepts an object
    `{"old":"new", …}` or a list `[{"old":..,"new":..}, …]`; ignores malformed
    entries (the caller re-validates every pair)."""
    out: dict[str, str] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if (isinstance(k, str) and isinstance(v, str)
                    and k.strip() and v.strip()):
                out[k.strip()] = v.strip()
    elif isinstance(data, list):
        for it in data:
            if (isinstance(it, dict) and isinstance(it.get("old"), str)
                    and isinstance(it.get("new"), str)):
                o, n = it["old"].strip(), it["new"].strip()
                if o and n:
                    out[o] = n
    return out


def _valid_renames(proposed: "dict[str, str]", *, own_leaves: "set[str]",
                   existing_leaves: "set[str]") -> "dict[str, str]":
    """Keep only safe rename pairs: `old` ∈ this file's renamable survivors,
    `new` a fresh valid identifier — distinct, not colliding with any other
    domain decl's leaf, not equal to any proposed `old` (no rename chains /
    swaps), not a duplicate target. The per-file rebuild gate is the real
    correctness check; this is the cheap structural pre-filter."""
    olds = set(proposed)
    seen_new: "set[str]" = set()
    out: dict[str, str] = {}
    for old, new in proposed.items():
        if "." in old:
            # A namespace-extension decl (`DiffForm.integral`): consumers may
            # reference it via TERM dot-notation (`φ.integral`), which no
            # token rewrite can see — a same-file break is caught by the
            # rebuild gate, but a CROSS-file consumer self-applies the rename
            # later (deferred-rewire) and strands red. Renaming these is not
            # mechanically safe; skip.
            continue
        if (old in own_leaves and _IDENT_RE.match(new) and new != old
                and new not in olds and new not in seen_new
                and new not in existing_leaves):
            out[old] = new
            seen_new.add(new)
    return out


def spawn_collect(workspace: Path, problem: str, prompt_path: Path,
                  context_text: str, output_names: "list[str]"
                  ) -> "dict[str, str] | None":
    """One pipeline-managed librarian spawn — the shared prelude of every
    agentic cleanup stage. Writes `context_text` as the attempt's `Context.md`,
    spawns the agent (`kind="librarian"`, `prompt_path`), then reads each
    requested output file from the attempts dir. Returns `{name: text}` for
    each output that exists, or None when the spawn failed (rc != 0) or the
    FIRST output name — the stage's mandatory artifact — is missing. Optional
    sidecars (later names) are simply absent from the dict."""
    from .... import agent
    attempts = agent.attempts_dir_for(workspace, agent.new_pipeline_id())
    (attempts / "Context.md").write_text(context_text, encoding="utf-8")
    rc = agent.spawn_llm(
        kind="librarian", prompt_path=prompt_path,
        problem_dir=workspace.joinpath("Problems", *problem.split(".")),
        attempts_dir=attempts, session_id=agent.new_pipeline_id())
    if rc != 0 or not (attempts / output_names[0]).exists():
        return None
    out: dict[str, str] = {}
    for name in output_names:
        p = attempts / name
        if p.exists():
            out[name] = p.read_text(encoding="utf-8")
    return out
