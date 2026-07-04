"""librarian.gate — split out of the former pipeline/librarian.py monolith."""
from __future__ import annotations

import re
from pathlib import Path as _Path
from ...state import db

from ._base import MigrateResult, _code_normalized
from .astslice import _NOMINAL_KINDS, _defs_decl_fqn, _nominal_decl_src, extract_decl_fq_name, extract_decl_kind, extract_decls


def _verbatim_nominal_ok(patch_text: str, *, problem: str, target_slug: str,
                         target_module: str, workspace: "_Path") -> bool:
    """Gate D's nominal special-case: True iff the migrated declaration's
    source equals the Defs.lean source — `_code_normalized` (comments
    stripped, whitespace collapsed) and modulo namespace qualification
    (`Problems.<p>.X` / `<target_module>.X` both normalize to bare `X`)."""
    dl = db.problem_dir(workspace, problem) / "Defs.lean"
    if not dl.exists():
        return False
    src = _nominal_decl_src(dl.read_text(encoding="utf-8"), target_slug)
    out = _nominal_decl_src(patch_text, target_slug)
    if src is None or out is None:
        return False

    def _norm(s: str) -> str:
        s = s.replace(f"Problems.{problem}.", "")
        s = s.replace(f"{target_module}.", "")
        return _code_normalized(s)

    return _norm(src) == _norm(out)


def migrate_defeq_gate(
    patch_text: str, *, problem: str, target_slug: str,
    defs_decls: "list[str]", target_module: str,
    target_fq: "str | None" = None, kind: "str | None" = None,
    defeq_verifier=None, workspace: "_Path | None" = None,
) -> MigrateResult:
    """Gate D for the migrate path — the def-tampering guard (plan §2).

    Only Defs-originated declarations are checked; a regular migrated
    lemma passes untouched. The kernel can't prove a strong root from a
    weakened lemma, so lemmas need no defeq pin — only a `def` body, which
    spans a statement's hypothesis AND conclusion, can be silently
    tampered while every other gate still passes.

      - `target_slug` not in `defs_decls` → ok (not a Defs decl).
      - structure / class / inductive Defs decl → fail (nominal; `rfl`
        cannot equate two declarations — decline-and-flag for a verbatim
        special-case).
      - def / abbrev Defs decl → `@Problems.<p>.<slug> = @<target> := rfl`
        must elaborate (via `gates.check_def_equivalence`). The probe
        imports the problem's Defs and the migrated Library module, so the
        caller MUST have the Library file on disk before calling.

    `defeq_verifier` is injectable (forwarded to check_def_equivalence) so
    unit tests run gateway-free. `target_fq`/`kind` may be supplied
    explicitly (per-file migrate, where the patch holds several decls and
    the positional pairing already knows this slug's name and keyword); if
    omitted they fall back to the patch's first declaration (single-decl
    callers and tests)."""
    if target_slug not in defs_decls:
        return MigrateResult(True, "")
    if kind is None:
        kind = extract_decl_kind(patch_text)
    if kind in _NOMINAL_KINDS:
        # Verbatim special-case: `rfl` cannot equate two separate nominal
        # declarations, but the tampering guard holds just as well if the
        # migrated declaration's SOURCE is the Defs source verbatim
        # (comments stripped, whitespace-normalized, modulo namespace
        # qualification) — same field names and types, elaborated under the
        # same replayed context the assembly carries. The mechanical path
        # produces exactly that, so this passes by construction and still
        # catches a corrupted assembly or a future agentic rewrite
        # (stokes_integral `class OrientedManifold`, 2026-06-12).
        if workspace is not None and _verbatim_nominal_ok(
                patch_text, problem=problem, target_slug=target_slug,
                target_module=target_module, workspace=workspace):
            return MigrateResult(True, "")
        return MigrateResult(
            False, f"Gate D: Defs decl `{target_slug}` is a {kind} "
                   "(nominal) — `rfl` cannot equate two separate "
                   "declarations, and the migrated source is NOT verbatim-"
                   "equal to the Defs source (or Defs.lean unavailable).")
    if target_fq is None:
        target_fq = extract_decl_fq_name(patch_text)
    if target_fq is None:
        return MigrateResult(
            False, "Gate D: could not extract the migrated declaration's "
                   "name (anonymous or malformed decl)")
    from ...quality.librarian import gates
    # Real FQN of the Defs decl — a decl declared under a foreign namespace
    # (residue_thm's `windingNumber` lives at `Complex.windingNumber`, not
    # `Problems.residue_thm.windingNumber`) would otherwise make the probe
    # reference an unknown identifier and STALL the file (the relabel path was
    # fixed in 9f095fd; this Gate-D path is its sibling).
    defs_fq = f"Problems.{problem}.{target_slug}"
    if workspace is not None:
        try:
            defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
            defs_text = defs_path.read_text(encoding="utf-8")
            from ...lsp.decl_oracle import DeclOracle
            defs_fq = _defs_decl_fqn(
                defs_text, target_slug, problem=problem,
                oracle=DeclOracle.cached_for_file(defs_path,
                                                  workspace=workspace))
        except OSError:
            pass
    # #43 namespace-preserved Defs decl: a decl the operator authored under a
    # foreign namespace (e.g. `Complex.windingNumber`) keeps that SAME
    # fully-qualified name in the Library, so `defs_fq == target_fq`. The
    # cross-module defeq probe below imports BOTH `Problems.<p>.Defs` and the
    # Library module — both now define `Complex.windingNumber`, so the probe
    # dies with "environment already contains 'Complex.windingNumber'". It is
    # also unnecessary: the migrated copy is the byte-identical original (#43
    # preserves it verbatim), so verify by SOURCE equality instead — no dual
    # import, no collision. (relabelled Defs decls keep `defs_fq != target_fq`,
    # so they still take the defeq path below.)
    if defs_fq == target_fq:
        if workspace is not None and _verbatim_nominal_ok(
                patch_text, problem=problem, target_slug=target_slug,
                target_module=target_module, workspace=workspace):
            return MigrateResult(True, "")
        return MigrateResult(
            False, f"Gate D: namespace-preserved Defs decl `{target_slug}` "
                   f"({defs_fq}) is not verbatim-equal to its Defs source")
    res = gates.check_def_equivalence(
        defs_fq, target_fq,
        imports=[f"Problems.{problem}.Defs", target_module],
        verifier=defeq_verifier, workspace=workspace)
    if res.ok:
        return MigrateResult(True, "")
    # A def whose SIGNATURE mentions a nominal Defs sibling can never be
    # rfl-defeq across the migration boundary — the Problems and Library
    # copies of that class are two distinct declarations, so the two sides
    # of `@a = @b` don't even share a type (stokes_integral
    # `DiffForm.integral [OrientedManifold I N]`, 2026-06-12). Verbatim
    # source equality is a strictly stronger tampering guard than defeq
    # (identical text ⟹ untampered), so accept it as the fallback; a
    # genuinely tampered def fails both.
    if workspace is not None and _verbatim_nominal_ok(
            patch_text, problem=problem, target_slug=target_slug,
            target_module=target_module, workspace=workspace):
        return MigrateResult(True, "")
    return MigrateResult(False, "; ".join(res.issues))


def _uses_sorry(text: str) -> bool:
    """True iff `text` actually USES the `sorry` term/tactic — ignoring
    comments. A `--` line comment or `/- … -/` (incl. `/-- … -/` doc) comment
    may legitimately contain the word 'sorry' (e.g. a note 'Builds sorry-free'),
    which a naive `"sorry" in text` substring check wrongly flags. The kernel
    axiom probe (sorryAx ∉ whitelist) is the authoritative detector; this is a
    fast, clear pre-check, so a comment-stripped word-boundary scan suffices.
    `sorry` as an identifier prefix (`sorry_free`) is safe — `_` is a word char,
    so `\\bsorry\\b` won't match it."""
    import re as _r
    no_block = _r.sub(r"/-.*?-/", " ", text, flags=_r.DOTALL)  # /- … -/, /-- -/
    no_line = _r.sub(r"--[^\n]*", " ", no_block)               # -- line comments
    return bool(_r.search(r"\bsorry\b", no_line))


_AXIOM_DECL_RE = re.compile(
    # line-anchored declaration head (optional attrs / visibility modifiers),
    # plus the `set_option … in axiom` same-line form.
    r"(?:^\s*(?:@\[[^\]]*\]\s*)*(?:private\s+|protected\s+)?|\bin\s+)axiom\s",
    re.MULTILINE)


def _declares_axiom(text: str) -> bool:
    """True iff `text` DECLARES an `axiom` — ignoring comments (a doc comment
    may legitimately discuss axioms). The Library must never introduce axioms:
    a REFERENCED rogue axiom is caught by the per-decl `#print axioms` probe
    (it appears in the referrer's transitive set), and a top-level named axiom
    self-reports under its own probe line — but this cheap text scan fails
    fast with a clear message and also covers forms the decl extractor might
    not surface. Audit's whole-file rewrite is the live vector: its gate pins
    only the LISTED decls' types and does not forbid ADDING declarations."""
    no_block = re.sub(r"/-.*?-/", " ", text, flags=re.DOTALL)
    no_line = re.sub(r"--[^\n]*", " ", no_block)
    return bool(_AXIOM_DECL_RE.search(no_line))


def migrate_commit_gate(
    patch_text: str, target_path: "_Path", *,
    whitelist: "list[str] | None" = None,
    probe_verifier=None,
    workspace: "_Path | None" = None,
) -> MigrateResult:
    """Decide whether a migrate patch may be committed to its Library
    file. Hard checks (plan §2 Gate A + build + per-file axiom check):

      1. import-closure — patch imports only Mathlib/Library (Gate A).
      2. build + axiom check — ONE warm-gateway elaboration. The probe text
         is the file plus a `#print axioms <fq>` per declaration; that single
         build yields BOTH the build diagnostics (0 errors, 0 sorry) AND every
         decl's transitive axiom set (emitted as `info` diagnostics). When a
         `whitelist` is set, each decl's axioms must be ⊆ whitelist (operator's
         authorized axioms). `build` alone accepts a file whose imports carry
         `sorry`; only `#print axioms` walks the kernel graph.

         Injectable as `probe_verifier(probe_text) -> (build_ok, build_detail,
         axioms_map[, decl_info])` so tests run without a gateway; defaults to
         the real warm probe (which appends the elaboration's decl_info — the
         kernel-true decl list backing the probe-coverage cross-check; a
         3-tuple skips that check). `whitelist=None` skips the axiom check
         (and the `#print axioms` lines) — unit tests that only exercise
         closure/build don't pass one.

         This replaces the old build + per-decl axiom re-elaboration loop: a
         147-decl file went from ~148 full elaborations to 1.

    Does NOT write anything — the caller (migrate parse_fn) does the
    file copy + `mark_library_migrated` on ok=True.
    """
    from ...quality.librarian import gates

    closure = gates.check_import_closure_text(
        patch_text, label=target_path.name)
    if not closure.ok:
        return MigrateResult(False, "; ".join(closure.issues))

    if _uses_sorry(patch_text):
        # Cheap pre-check (comment-aware; the kernel axiom probe below is the
        # authoritative sorryAx detector). A clear message here beats a generic
        # "declaration uses sorry" diagnostic.
        return MigrateResult(False, "patch still contains `sorry`")

    if _declares_axiom(patch_text):
        return MigrateResult(
            False, "patch declares an `axiom` — the Library must never "
                   "introduce axioms (prove it or cite Mathlib)")

    # Per-file axiom invariant needs a named decl for every declaration. Only
    # extracted when a whitelist is set (the axiom probe needs the fq names);
    # an anonymous/malformed patch then fails honestly rather than silently
    # skipping the check.
    decls = extract_decls(patch_text) if whitelist is not None else []
    if whitelist is not None and not decls:
        return MigrateResult(
            False, "axiom check: no named declaration found "
                   "(anonymous or malformed patch)")

    if probe_verifier is None:
        probe_verifier = _warm_probe_verifier(workspace)
    check_names = [d.fq_name for d in decls if d.fq_name]
    probe_text = (patch_text if whitelist is None
                  else _axiom_probe_text(patch_text, check_names))
    # Injectable test verifiers return the historical 3-tuple; the real
    # warm verifier appends the elaboration's decl_info (4th slot).
    probe_out = probe_verifier(probe_text)
    build_ok, build_detail, axioms_map = probe_out[:3]
    kernel_info = probe_out[3] if len(probe_out) > 3 else None
    if not build_ok:
        return MigrateResult(False, f"build failed: {build_detail}")

    if whitelist is not None and kernel_info:
        # Probe-COVERAGE cross-check (declInfo oracle): every top-level
        # declaration the kernel actually saw must have a `#print axioms`
        # line. The text extractor under-extracting (anonymous instance,
        # a decl shape its regex doesn't know) used to mean that decl's
        # axioms were silently never checked — a narrowing of the axiom
        # gate, not a failure. Self-heal ONCE: re-probe with the union
        # list (kernel-true names resolve at top level by construction).
        from ...lsp.decl_oracle import primary_user_names
        kernel_names = [n for n in primary_user_names(kernel_info)]
        missing = [n for n in kernel_names if n not in set(check_names)]
        if missing:
            print(f"[librarian] axiom-probe coverage gap: extractor "
                  f"missed {missing} — re-probing with the kernel-true "
                  f"decl list", flush=True)
            check_names = check_names + missing
            probe_out = probe_verifier(
                _axiom_probe_text(patch_text, check_names))
            build_ok, build_detail, axioms_map = probe_out[:3]
            if not build_ok:
                return MigrateResult(
                    False, f"coverage re-probe build failed: {build_detail}")

    if whitelist is not None:
        wl = set(whitelist)
        for fq in check_names:
            used = axioms_map.get(fq)
            if used is None:
                return MigrateResult(
                    False, f"axiom check failed for `{fq}`: no "
                           "`#print axioms` report in the build output "
                           "(probe omitted or name unresolved)")
            rogue = used - wl
            if rogue:
                return MigrateResult(
                    False, f"axiom check failed for `{fq}`: "
                           f"rogue axioms: {sorted(rogue)}")
    return MigrateResult(True, "")


_AX_DEP_RE = re.compile(
    r"^'(?P<fq>.+?)' depends on axioms:\s*\[(?P<ax>.*)\]\s*$", re.DOTALL)
_AX_NONE_RE = re.compile(
    r"^'(?P<fq>.+?)' does not depend on any axioms\s*$", re.DOTALL)


def _axiom_probe_text(patch_text: str, fq_names: "list[str]") -> str:
    """Append a `#print axioms <fq>` per declaration so ONE build elaboration
    also emits every decl's transitive axiom set (as `info` diagnostics). The
    commands sit after the file body — full names resolve at top level — and
    appear ONLY in this throwaway probe; the committed file never carries
    them. Empty / nameless list → the file unchanged (build-only probe)."""
    lines = [f"#print axioms {fq}" for fq in fq_names if fq]
    if not lines:
        return patch_text
    sep = "" if patch_text.endswith("\n") else "\n"
    return patch_text + sep + "\n".join(lines) + "\n"


def _parse_axiom_diags(diagnostics) -> "dict[str, set[str]]":
    """Parse `#print axioms` `info` diagnostics into `{fq: {axioms}}`. The
    Lean output is stable: `'<fq>' depends on axioms: [a, b]` or
    `'<fq>' does not depend on any axioms`. Keyed by the fq name the message
    carries, so attribution survives line shifts."""
    out: dict = {}
    for d in diagnostics or []:
        if d.get("severity") != "info":
            continue
        msg = (d.get("message") or "").strip()
        m = _AX_DEP_RE.match(msg)
        if m:
            out[m.group("fq")] = {a.strip()
                                  for a in m.group("ax").split(",")
                                  if a.strip()}
            continue
        m = _AX_NONE_RE.match(msg)
        if m:
            out[m.group("fq")] = set()
    return out


def _warm_probe_verifier(workspace):
    """Default probe_verifier: write the probe text (the file + `#print axioms`
    commands) to a temp file under `Library/`, run ONE warm-gateway build, and
    return `(build_ok, build_detail, axioms_map, decl_info)`. The single elaboration
    yields both the build result (error diagnostics) and every decl's
    transitive axiom set (info diagnostics) — replacing the old separate build
    + per-decl axiom re-elaboration. The temp file lives under `Library/` so
    the gateway resolves the Library import path; it is removed after."""
    import os
    import tempfile

    def _verify(probe_text: str):
        from ...lsp import lifecycle as gateway_lifecycle
        ws = workspace or _Path(".")
        libdir = ws / "Library"
        libdir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=".lean", prefix="_migrate_probe_",
                                   dir=str(libdir))
        tmp_path = _Path(tmp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(probe_text)
            # decl_info rides the SAME elaboration: the kernel-true decl
            # list backs the probe-coverage cross-check in
            # migrate_commit_gate (a decl the text scan missed = a decl
            # whose axioms were never probed). Best-effort — an old
            # gateway/binary yields decl_info=None and the gate skips
            # the cross-check, i.e. pre-oracle behavior.
            r = gateway_lifecycle.verify_file(
                tmp_path, write_olean=False, decl_info=True, workspace=ws)
            if "error" in r and r.get("error"):
                return (False, f"verify infra error: {r['error']}", {}, None)
            axioms_map = _parse_axiom_diags(r.get("diagnostics"))
            decl_info = r.get("decl_info")
            if not r.get("ok"):
                errs = "; ".join(
                    d.get("message", "")[:120]
                    for d in (r.get("diagnostics") or [])
                    if d.get("severity") == "error"
                )[:300]
                return (False, errs or "(no error diagnostics)", axioms_map,
                        decl_info)
            return (True, "", axioms_map, decl_info)
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return _verify


def _warm_olean_writer(workspace):
    """Default olean_writer: build the committed Library file and persist its
    `.olean` (write_olean=True), so a later-dispatched importer builds against
    a FRESH dependency olean — proof-time does the same per proved lemma
    (builder.py). The gateway's `lake serve` imports deps from on-disk oleans
    and does NOT rebuild stale ones, so without this every cross-file build
    (migrate / cleanup re-gate / bridge) risks a stale dependency (R1b)."""
    def _write(target_path) -> tuple[bool, str]:
        from ...lsp import lifecycle as gateway_lifecycle
        ws = workspace or _Path(".")
        r = gateway_lifecycle.verify_file(
            target_path, write_olean=True, workspace=ws)
        if r.get("error"):
            return False, f"olean write infra error: {r['error']}"
        if not r.get("ok"):
            errs = "; ".join(
                d.get("message", "")[:120]
                for d in (r.get("diagnostics") or [])
                if d.get("severity") == "error")[:300]
            return False, errs or "(build failed on olean write)"
        if not r.get("olean_written"):
            return False, "olean not written"
        return True, ""
    return _write
