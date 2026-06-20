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


def _decl_line_spans(text: str, names: "set[str]") -> "set[int]":
    """1-based line numbers covered by each declaration in `names` — its header
    line through the line before the next top-level decl/`variable`/`section`/
    `end`/`namespace`. Used to skip frozen (Defs-origin) decls in the location-
    based `_`-prefix pass, which is not decl-list-driven."""
    if not names:
        return set()
    lines = text.split("\n")
    heads = []
    for i, ln in enumerate(lines):
        m = _DECL_NAME_RE.match(ln)
        if m and m.group(1) in names:
            heads.append(i)                          # 0-based header line
    if not heads:
        return set()
    boundary = re.compile(
        r"(?m)^\s*(?:@\[|noncomputable\b|private\b|protected\b|scoped\b|"
        r"def\b|abbrev\b|theorem\b|lemma\b|structure\b|class\b|inductive\b|"
        r"instance\b|variable\b|section\b|end\b|namespace\b)")
    out: "set[int]" = set()
    for h in heads:
        j = h + 1
        while j < len(lines) and not boundary.match(lines[j]):
            j += 1
        for k in range(h, j):                        # 0-based → 1-based
            out.add(k + 1)
    return out


def file_cleanup_underscore_unused_hyps(workspace: Path, problem: str,
                                        target_file: str, *,
                                        frozen: "set[str] | None" = None
                                        ) -> bool:
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
    if frozen:
        # Never `_`-prefix a binder inside a frozen (Defs-origin) decl — that
        # would edit the canonical definition's source. Occurrences are in the
        # injected `scan` space, so compute the frozen spans in `scan` too.
        frozen_lines = _decl_line_spans(scan, frozen)
        occ = [o for o in occ if o[0] not in frozen_lines]
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


# --- linter.style.whitespace + linter.style.emptyLine (text-based) -----------
# These two mathlib STYLE linters fire ONLY on a real registered-module
# `lake build` — a throwaway `lake env lean` (what every other mechanical gate
# uses) does NOT trigger them, even with `set_option linter.style.whitespace
# true` forced on (verified 2026-06-20). They are also NOT in
# `linter.mathlibStandardSet`, so the cold per-file zero-warning gate misses
# them too. But the audit agent's LSP `errors_at` (real `lake serve`) DOES
# surface them, and audit.md tells it to drive every warning to zero — so on a
# machine-dense file it hand-fixes 100+ `(0:ℝ)`→`(0 : ℝ)` spacings one ~25s LSP
# re-elaboration at a time and times out (residue HomotopyIntegral: 141
# whitespace + 4 emptyLine → all 3 audit cold passes hit the 960s cap). This
# pass clears them mechanically in the `unused` stage BEFORE decide/audit, so the
# agent only ever sees genuine semantic work.
# `lake build` prints `warning: <file>:<L>:<C>: <message>` (the `warning:` token
# leads the line — UNLIKE `lake env lean`'s `<file>:<L>:<C>: warning: <message>`),
# so anchor on the `:<L>:<C>: <message>` tail, which is identical in both.
_WS_HEAD_RE = re.compile(r":(\d+):\d+: missing space in the source")
_EMPTYLINE_RE = re.compile(
    r":(\d+):\d+: Please, write a comment here or remove this line")
_WS_MAX_PASSES = 4


def _parse_whitespace_warnings(build_output: str, basename: str
                               ) -> "dict[int, set[str]]":
    """`linter.style.whitespace` → `{line_1based: {GOOD, …}}`. Each warning is a
    block:
        <file>:<L>:<C>: warning: missing space in the source
        <blank> / `This part of the code` / `  '<BAD>'` /
        `should be written as` / `  '<GOOD>'`
    The fix is content-anchored — `GOOD` with its spaces removed is exactly the
    cramped form to replace (`(0 : ℝ)` → `(0:ℝ)`), so the column (byte / UTF-16 /
    codepoint-ambiguous on a `ℝ` line) is never needed. Filtered to `basename`
    (deps are cached, but be defensive)."""
    out: "dict[int, set[str]]" = {}
    lines = build_output.splitlines()
    for i, ln in enumerate(lines):
        m = _WS_HEAD_RE.search(ln)
        if not m or basename not in ln:
            continue
        L = int(m.group(1))
        for j in range(i + 1, min(i + 7, len(lines))):
            if lines[j].strip() == "should be written as" and j + 1 < len(lines):
                g = lines[j + 1].strip()
                if len(g) >= 3 and g[0] == "'" and g[-1] == "'":
                    out.setdefault(L, set()).add(g[1:-1])
                break
    return out


def _parse_emptyline_warnings(build_output: str, basename: str) -> "list[int]":
    """`linter.style.emptyLine` → the 1-based line numbers flagged (each IS the
    offending blank line). Filtered to `basename`."""
    return sorted({int(m.group(1))
                   for ln in build_output.splitlines()
                   if basename in ln and (m := _EMPTYLINE_RE.search(ln))})


def _apply_whitespace_fixes(text: str,
                            by_line: "dict[int, set[str]]") -> "tuple[str, int]":
    """Per flagged line, replace every cramped `GOOD.replace(' ', '')` with
    `GOOD`. Longest GOOD first (so a core that is a substring of another doesn't
    pre-empt the wider fix). Per-line scope + acting only on cores the linter
    emitted keeps the blast radius minimal; the caller rebuild-gates. Returns
    `(new_text, n_lines_changed)`."""
    lines = text.split("\n")
    changed = 0
    for L, goods in by_line.items():
        if L < 1 or L > len(lines):
            continue
        s = orig = lines[L - 1]
        for good in sorted(goods, key=lambda g: -len(g)):
            core = good.replace(" ", "")
            if core and core != good and core in s:
                s = s.replace(core, good)
        if s != orig:
            lines[L - 1] = s
            changed += 1
    return "\n".join(lines), changed


def _apply_emptyline_fixes(text: str, occ: "list[int]") -> "tuple[str, int]":
    """Delete each flagged blank line, highest line number first so earlier
    line numbers stay valid. A line that is NOT actually blank (stale diagnostic)
    is skipped — never a corruption. Returns `(new_text, n_deleted)`."""
    lines = text.split("\n")
    deleted = 0
    for L in sorted(occ, reverse=True):
        if 1 <= L <= len(lines) and lines[L - 1].strip() == "":
            del lines[L - 1]
            deleted += 1
    return "\n".join(lines), deleted


def _force_module_rebuild(workspace: Path, target_file: str) -> None:
    """Remove a module's build artifacts so the next `lake build` re-elaborates
    it (and re-emits its text-style lints — `lake` caches on a content hash, so
    touching mtime is NOT enough; verified 2026-06-20). Best-effort."""
    stem = target_file[:-5] if target_file.endswith(".lean") else target_file
    for art in (f".lake/build/lib/lean/{stem}.olean",
                f".lake/build/lib/lean/{stem}.olean.hash",
                f".lake/build/lib/lean/{stem}.trace"):
        try:
            (workspace / art).unlink()
        except OSError:
            pass


def file_cleanup_normalize_whitespace(workspace: Path, problem: str,
                                      target_file: str, *,
                                      frozen: "set[str] | None" = None) -> bool:
    """Mechanically clear `linter.style.whitespace` + `linter.style.emptyLine` —
    the text-based mathlib style linters the audit agent otherwise burns its
    whole spawn budget hand-fixing (see the module note above). Detection needs a
    REAL module build (these linters don't fire on the throwaway `lake env lean`
    the other gates use), so we drop the module's olean to force a re-elaboration
    and parse its warnings. Content-anchored + rebuild-gated; skips frozen
    (Defs-origin) decl spans. Iterates (a fix can reveal a straggler on a shared
    line) up to `_WS_MAX_PASSES` — each write is itself a rebuild that re-emits
    the remaining lints, so it doubles as the gate AND the next detection. Writes
    on green rebuilds; reverts the last bad batch. Returns whether it changed the
    file."""
    leaf = target_file.split("/")[-1]
    module = C._mod_of_rel(target_file)
    from ....pipeline._lake import lake_build_modules
    path = workspace / target_file
    try:
        original = path.read_text(encoding="utf-8")
    except OSError:
        return False
    # Pre-flight: any imported Library oleans the detection build needs.
    missing = C._missing_oleans(workspace, re.findall(
        r"^\s*import\s+(Library\.[\w.]+)", original, re.M))
    if missing:
        try:
            lake_build_modules(workspace, missing)
        except Exception:  # noqa: BLE001 — best-effort pre-flight
            pass
    _force_module_rebuild(workspace, target_file)     # force the first detection
    ok, out = lake_build_modules(workspace, [module])
    if not ok:
        return False                                  # file itself doesn't build
    text = original
    total_ws = total_el = 0
    for _it in range(_WS_MAX_PASSES):
        by_line = _parse_whitespace_warnings(out, leaf)
        el = _parse_emptyline_warnings(out, leaf)
        if frozen:                            # never touch a frozen decl's source
            fr = _decl_line_spans(text, frozen)
            by_line = {L: g for L, g in by_line.items() if L not in fr}
            el = [L for L in el if L not in fr]
        if not by_line and not el:
            break                             # converged: zero text-style lints
        cand, nws = _apply_whitespace_fixes(text, by_line)
        cand, nel = _apply_emptyline_fixes(cand, el)
        if cand == text:
            break                             # only stale diagnostics — stop
        path.write_text(cand, encoding="utf-8")       # a content change → rebuild
        ok, out = lake_build_modules(workspace, [module])
        if not ok:
            path.write_text(text, encoding="utf-8")   # revert to last green batch
            out = ""
            print(f"[staged] normalize-whitespace `{leaf}` — reverted last batch "
                  f"(rebuild failed)", flush=True)
            break
        text, total_ws, total_el = cand, total_ws + nws, total_el + nel
    if text == original:
        return False
    print(f"[staged] normalize-whitespace `{leaf}` — fixed {total_ws} whitespace "
          f"line(s) + removed {total_el} empty line(s)", flush=True)
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
