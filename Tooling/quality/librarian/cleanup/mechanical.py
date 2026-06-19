"""§13 mechanical file-cleanup stages — unused-arg removal + framework-comment
strip. No agent spawn; both are rebuild-gated mechanical rewrites."""
from __future__ import annotations

import re
from pathlib import Path

from . import _common as C
from ._common import _DECL_NAME_RE, _Decl


_UNUSED_HYP_HEAD = re.compile(
    r"`([A-Za-z_][\w'.]*)` does not use the following hypotheses in its type")
_UNUSED_HYP_BULLET = re.compile(r"^\s*[•·]\s*(.+?)\s*\(#\d+\)\s*$")


def _parse_unused_hyps(build_output: str) -> "dict[str, list[str]]":
    """Parse mathlib's `unusedArguments` linter → {decl_leaf: [binder_text]}.
    Each warning is `\\`decl\\` does not use the following hypotheses in its type:`
    followed by bullet lines `• <binder> (#N)`. Binder text is verbatim
    (`[DecidableEq α]`, `(h : P)`, …)."""
    out: "dict[str, list[str]]" = {}
    lines = build_output.splitlines()
    i = 0
    while i < len(lines):
        m = _UNUSED_HYP_HEAD.search(lines[i])
        if not m:
            i += 1
            continue
        name, binders, j = m.group(1), [], i + 1
        while j < len(lines):
            b = _UNUSED_HYP_BULLET.match(lines[j])
            if not b:
                break
            binders.append(" ".join(b.group(1).split()))
            j += 1
        if binders:
            out.setdefault(name, []).extend(binders)
        i = j if j > i else i + 1
    return out


def _strip_instance_binders(text: str, name: str,
                            binders: "list[str]") -> "tuple[str, bool]":
    """Remove each `[…]` instance binder in `binders` from decl `name`'s header
    (the span between its name and the proof `:=`). String-exact (the binder is
    'unused in type' → it cannot appear in the conclusion, so the only match in
    the header is the binder itself). Returns `(new_text, changed)`."""
    m = next((h for h in _DECL_NAME_RE.finditer(text) if h.group(1) == name), None)
    if m is None:
        return text, False
    pa = C._proof_assign_pos(text, m.start())
    if pa < 0:
        return text, False
    lo, hi = m.end(), pa
    region, changed = text[lo:hi], False
    for b in binders:
        if not b.startswith("["):
            continue                              # instance binders only (v1)
        for cand in (" " + b, b):
            if cand in region:
                region = region.replace(cand, "", 1)
                changed = True
                break
    return (text[:lo] + region + text[hi:], True) if changed else (text, False)


def _insert_classical(text: str, name: str) -> str:
    """Insert `classical` as the first tactic of decl `name`'s `by` proof (so a
    removed `[DecidableEq …]` the proof relied on is re-synthesized). Term-mode
    proofs are left untouched (v1 reverts those)."""
    m = next((h for h in _DECL_NAME_RE.finditer(text) if h.group(1) == name), None)
    if m is None:
        return text
    pa = C._proof_assign_pos(text, m.start())
    if pa < 0:
        return text
    mm = re.match(r":=\s*by\b", text[pa:])
    if not mm:
        return text
    at = pa + mm.end()
    return text[:at] + "\n  classical" + text[at:]


def file_cleanup_unused_args(workspace: Path, problem: str, target_file: str,
                             decls_in_file: "list[_Decl]") -> bool:
    """§13 P2 — drop signature hypotheses the mathlib `unusedArguments` linter
    flags as unused in the TYPE. MECHANICAL + rebuild-gated. v1 scope = **`[…]`
    instance binders only** (the machine-generated `[DecidableEq α]` bulk):
    consumer-safe — instances are auto-synthesized at call sites, so removal only
    GENERALIZES the lemma, no caller changes; `classical` re-synthesizes a
    Decidable the proof needed. Implicit `{…}` / explicit `(…)` (consumer-
    impacting) are deferred to a later LLM pass. Writes the file on a green
    rebuild; reverts (no-op) otherwise. Type-CHANGING → gated by rebuild, NOT the
    type-preserving #check used by the variable pass.

    v1 = the `unusedDecidableInType` linter only (classical re-synthesizes a
    `Decidable`). `unusedFintypeInType` wants `Fintype.ofFinite`/a `Finite`
    instance, not classical — deferred."""
    leaf = target_file.split("/")[-1]
    try:
        original = (workspace / target_file).read_text(encoding="utf-8")
    except OSError:
        return False
    missing = C._missing_oleans(workspace, re.findall(
        r"^\s*import\s+(Library\.[\w.]+)", original, re.M))
    if missing:
        from ....pipeline._lake import lake_build_modules
        try:
            lake_build_modules(workspace, missing)
        except Exception:  # noqa: BLE001 — best-effort pre-flight
            pass
    # detection build: force the (default-OFF) unused-Decidable linter on.
    scan = C._inject_linter(original, "linter.unusedDecidableInType")
    ok0, out0 = C._build_with_output(workspace, scan, prefix="_unused_scan")
    if not ok0:
        return False                              # file itself doesn't build — bail
    names = {d.name for d in decls_in_file}
    targets = {n: [b for b in bs if b.startswith("[")]
               for n, bs in _parse_unused_hyps(out0).items() if n in names}
    targets = {n: bs for n, bs in targets.items() if bs}
    if not targets:
        return False
    new_text, edited = original, []
    for name, binders in targets.items():
        nt, did = _strip_instance_binders(new_text, name, binders)
        if did:
            new_text, _ = nt, edited.append(name)
    if not edited:
        return False
    ok, detail = C._build_with_output(workspace, new_text, prefix="_unused_try")
    if not ok and re.search(r"(?i)synthesize|instance|Decidable", detail):
        nt = new_text
        for name in edited:
            nt = _insert_classical(nt, name)
        ok2, _d2 = C._build_with_output(workspace, nt, prefix="_unused_cls")
        if ok2:
            new_text, ok = nt, True
    if not ok:
        print(f"[staged] unused-args `{leaf}` — reverted (rebuild failed)",
              flush=True)
        return False
    n_hyp = sum(len(b) for b in targets.values())
    (workspace / target_file).write_text(new_text, encoding="utf-8")
    print(f"[staged] unused-args `{leaf}` — removed {n_hyp} instance hyp(s) "
          f"from {len(edited)} decl(s)", flush=True)
    return True


_UNUSED_VAR_RE = re.compile(
    r":(\d+):(\d+): warning: unused variable `([^`]+)`")


def _parse_unused_variables(build_output: str) -> "list[tuple[int, int, str]]":
    """Parse Lean's `linter.unusedVariables` warnings → `[(line_1based,
    col_0based, name), …]`. Each is `<file>:<L>:<C>: warning: unused variable
    \\`<name>\\``, where `C` is the 0-based codepoint column of the binder name's
    first char (verified: `    (hγ` → col 5 = the `h`). Distinct from
    `unusedArguments` (unused in TYPE, handled by `file_cleanup_unused_args`):
    this fires for a hypothesis binder unreferenced in the body AND the rest of
    the signature, so `_`-prefixing it is reference-free and safe."""
    return [(int(m.group(1)), int(m.group(2)), m.group(3))
            for m in _UNUSED_VAR_RE.finditer(build_output)]


def _underscore_unused_vars(text: str,
                            occ: "list[tuple[int, int, str]]"
                            ) -> "tuple[str, int]":
    """`_`-prefix each flagged unused binder at its exact `(line, col)`:
    `(hγ : …)` → `(_hγ : …)`. Edits are applied per line right-to-left (largest
    col first) so an inserted `_` never shifts a not-yet-applied col on the same
    line (two unused binders can share a line). A location is skipped unless the
    `name` token sits exactly at `col` and isn't already `_`-prefixed — so a
    stale/mismatched diagnostic is a no-op, never a corruption. Returns
    `(new_text, n_prefixed)`."""
    lines = text.split("\n")
    by_line: "dict[int, list[tuple[int, str]]]" = {}
    for ln, col, nm in occ:
        by_line.setdefault(ln, []).append((col, nm))
    changed = 0
    for ln, items in by_line.items():
        if ln < 1 or ln > len(lines):
            continue
        s = lines[ln - 1]
        for col, nm in sorted(items, key=lambda x: -x[0]):
            if (0 <= col <= len(s) - len(nm)
                    and s[col:col + len(nm)] == nm
                    and not (col > 0 and s[col - 1] == "_")):
                s = s[:col] + "_" + s[col:]
                changed += 1
        lines[ln - 1] = s
    return "\n".join(lines), changed


def file_cleanup_underscore_unused_hyps(workspace: Path, problem: str,
                                        target_file: str) -> bool:
    """Mechanically `_`-prefix every binder the `linter.unusedVariables` lint
    flags as unused — the audit.md-prescribed fix ((h : …) → (_h : …)), done in
    ONE rebuild instead of N slow audit-agent LSP round-trips.

    Why a mechanical pass (residue 2026-06-19): big files (SimplyConnectedIntegral
    21-decl, LaurentDecompOuter 26-decl) carry 12+ unused hypothesis binders — a
    standard hypothesis bundle repeated across sibling lemmas, several unused in
    each. Left to the audit agent, each `_`-prefix is a ~25-30s re-elaboration
    round-trip on a 1000+-line file, so it times out (960s cap) before clearing
    them all → the hard zero-warning gate fails → STALL. `_`-prefixing is
    type-preserving and reference-free (the lint fires only when the name is
    unreferenced anywhere), so it is mechanical + rebuild-gated, like
    `file_cleanup_unused_args` (which handles the orthogonal `unusedArguments`
    type-unused INSTANCE binders). Runs in the `unused` stage BEFORE decide/audit,
    so audit's #check baseline already reflects the `_`-prefixed binders.

    Writes on a green rebuild; reverts (no-op) otherwise. Returns whether it
    changed the file."""
    leaf = target_file.split("/")[-1]
    try:
        original = (workspace / target_file).read_text(encoding="utf-8")
    except OSError:
        return False
    missing = C._missing_oleans(workspace, re.findall(
        r"^\s*import\s+(Library\.[\w.]+)", original, re.M))
    if missing:
        from ....pipeline._lake import lake_build_modules
        try:
            lake_build_modules(workspace, missing)
        except Exception:  # noqa: BLE001 — best-effort pre-flight
            pass
    # Detection build: same mathlib standard linter set the zero-warning gate
    # enforces, so we surface exactly the `unused variable` warnings that gate
    # would reject (unusedVariables is in the standard set). `_inject_linter`
    # prepends `set_option` lines, so the warning line numbers are in the INJECTED
    # text's coordinate space — apply the `_`-prefix there too (same space), then
    # strip the injected lines back out, or the offset mis-targets every binder.
    scan = C._inject_linter(original, *C._MATHLIB_LINT_OPTS)
    ok0, out0 = C._build_with_output(workspace, scan, prefix="_unusedvar_scan")
    if not ok0:
        return False                              # file itself doesn't build — bail
    occ = _parse_unused_variables(out0)
    if not occ:
        return False
    new_scan, n = _underscore_unused_vars(scan, occ)
    if n == 0 or new_scan == scan:
        return False
    new_text = new_scan
    for opt in C._MATHLIB_LINT_OPTS:              # remove the detection-only lines
        new_text = new_text.replace(f"set_option {opt} true\n", "", 1)
    if new_text == original:
        return False
    ok, _detail = C._build_with_output(workspace, new_text, prefix="_unusedvar_try")
    if not ok:
        print(f"[staged] underscore-unused `{leaf}` — reverted (rebuild failed)",
              flush=True)
        return False
    (workspace / target_file).write_text(new_text, encoding="utf-8")
    print(f"[staged] underscore-unused `{leaf}` — `_`-prefixed {n} unused "
          f"hypothesis binder(s)", flush=True)
    return True


_FW_COMMENT_MARKER = re.compile(
    r"entry_kind|sub-goal|\bcombinator\b|Closer:|\(was:|pad_and_place")


def file_cleanup_strip_framework_comments(workspace: Path, problem: str,
                                          target_file: str, *,
                                          session_token: "str | None" = None
                                          ) -> bool:
    """§13 (e) — strip framework-process `--` comment blocks that migrate carries
    from the proof: `entry_kind` tags + proof-search narration (`sub-goal` /
    `combinator` / `Closer:` / `(was: …)`). These describe HOW the proof was found
    — zero reader value, never in mathlib. Keeps `/-- … -/` docstrings and any
    `--` block WITHOUT a framework marker. Mechanical, comment-only; rebuild-gated
    against the rare case a stripped line sat inside a `/- … -/` block comment."""
    try:
        original = (workspace / target_file).read_text(encoding="utf-8")
    except OSError:
        return False
    lines = original.splitlines(keepends=True)
    out: "list[str]" = []
    i, n, stripped = 0, len(lines), 0
    while i < n:
        s = lines[i].lstrip()
        if s.startswith("--") and not s.startswith("/--"):   # a `--` comment block
            j = i
            while (j < n and lines[j].lstrip().startswith("--")
                   and not lines[j].lstrip().startswith("/--")):
                j += 1
            block = lines[i:j]
            if _FW_COMMENT_MARKER.search("".join(block)):
                stripped += len(block)                       # drop the whole block
            else:
                out.extend(block)
            i = j
        else:
            out.append(lines[i])
            i += 1
    if not stripped:
        return False
    new_text = "".join(out)
    missing = C._missing_oleans(workspace, re.findall(
        r"^\s*import\s+(Library\.[\w.]+)", original, re.M))
    if missing:
        from ....pipeline._lake import lake_build_modules
        try:
            lake_build_modules(workspace, missing)
        except Exception:  # noqa: BLE001
            pass
    ok, _d = C._lake_check(workspace, new_text, prefix="_fwcomment",
                           session_token=session_token)
    if not ok:
        return False
    (workspace / target_file).write_text(new_text, encoding="utf-8")
    print(f"[staged] strip-fw-comments `{target_file.split('/')[-1]}` — "
          f"removed {stripped} framework comment line(s)", flush=True)
    return True
