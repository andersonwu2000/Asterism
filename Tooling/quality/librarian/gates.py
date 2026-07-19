"""Librarian gates — deterministic framework-side checks.

These are the *mechanical judges* of the Librarian pipeline (plan §2).
The Librarian agent proposes Library files; these gates accept or reject
them without any judgement of their own.

Gate A — import-closure (this module, M2)
    Every Library file's `import` set must be a subset of
    {Mathlib.*, Library.*}. A Library that imports `Problems.*` or a
    problem's `Defs` is not self-contained — it still depends on the
    framework's per-problem scaffolding and could never be upstreamed
    (plan §1 north star).

Gate B — root re-derivation (M3, separate function below — stub for now)

The pure-text closure check is the authoritative fast gate. An optional
`build_verify=True` additionally runs the gateway lake build (the same
`gateway_lifecycle.verify_file` the proof pipelines use) to confirm the
file actually elaborates against only Mathlib + Library — catching a
file that passes the text check but references a Problems symbol via
`open`/full-qualification without an explicit import.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# Matches a Lean import line, tolerating the newer `public import` /
# `private import` module-system prefixes mathlib now emits. Captures the
# dotted module path. The pattern STRING is public — the one spelling of
# a Lean import line; other consumers (serve chapter) compile it with
# their own flags (re.M for whole-text scans).
IMPORT_LINE_PATTERN = (
    r"^\s*(?:public\s+|private\s+)?import\s+([A-Za-z_][\w.]*)\s*$")
_IMPORT_RE = re.compile(IMPORT_LINE_PATTERN)

# Roots a self-contained Library file is allowed to import.
_ALLOWED_ROOTS = ("Mathlib", "Library", "Init", "Std", "Batteries", "Lean")


@dataclass
class GateResult:
    ok: bool
    issues: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


def parse_imports(text: str) -> list[str]:
    """Return the dotted module paths imported by a Lean source string,
    in order. Ignores comments-only and non-import lines."""
    out: list[str] = []
    for line in text.splitlines():
        m = _IMPORT_RE.match(line)
        if m:
            out.append(m.group(1))
    return out


def _root_of(module: str) -> str:
    return module.split(".", 1)[0]


def check_import_closure_text(text: str, *, label: str = "<file>") -> GateResult:
    """Gate A core (pure text): assert every import's root is in
    `_ALLOWED_ROOTS`. Any `Problems.*` (or anything else outside the
    allow-list) is a violation."""
    issues: list[str] = []
    for mod in parse_imports(text):
        root = _root_of(mod)
        if root not in _ALLOWED_ROOTS:
            issues.append(f"{label}: forbidden import `{mod}` "
                          f"(root `{root}` not in {list(_ALLOWED_ROOTS)})")
    return GateResult(not issues, issues)


def check_import_closure(
    path: Path, *, build_verify: bool = False,
    workspace: Path | None = None,
) -> GateResult:
    """Gate A for a file on disk. Pure-text closure check always runs;
    `build_verify=True` additionally runs the gateway lake build to
    catch un-imported cross-references (slow — opt in)."""
    if not path.exists():
        return GateResult(False, [f"{path}: file does not exist"])
    text = path.read_text(encoding="utf-8", errors="replace")
    res = check_import_closure_text(text, label=path.name)
    if not res.ok or not build_verify:
        return res
    # Text check passed and caller wants the authoritative build.
    # NOTE: verify_file returns a dict (see lsp/lifecycle.py:170), not a
    # tuple — keys: ok / diagnostics / error / axioms.
    from ...lsp import lifecycle as gateway_lifecycle
    result = gateway_lifecycle.verify_file(
        path, write_olean=False, workspace=workspace)
    if not result.get("ok"):
        detail = result.get("error") or result.get("diagnostics")
        return GateResult(False, [f"{path.name}: build-verify failed "
                                  f"({detail})"])
    return GateResult(True, [])


def check_dir_import_closure(
    directory: Path, *, build_verify: bool = False,
    workspace: Path | None = None,
) -> GateResult:
    """Run Gate A over every `.lean` file under `directory`. Aggregates
    all issues so the operator sees the full violation set at once."""
    issues: list[str] = []
    for f in sorted(directory.rglob("*.lean")):
        r = check_import_closure(
            f, build_verify=build_verify, workspace=workspace)
        issues.extend(r.issues)
    return GateResult(not issues, issues)


# ---------------------------------------------------------------------
# Gate B — root re-derivation ("秒殺 root"), plan §2
# ---------------------------------------------------------------------

# A re-derivation proof should be a one-liner: `:= Library.foo args` or a
# short `by exact …` / `by simpa … using …`. If deriving the original root
# from the Library needs *real* work, the Library is missing a keystone
# (the completeness half of Gate B). This counts the proof-body tokens as
# a soft signal; the hard gates are import-closure + build + axiom_probe.
_REDERIVATION_TOKEN_BUDGET = 40


def _proof_body(text: str) -> str:
    """Everything after the theorem's body `:=` — best-effort. The
    bridge file is tiny (imports + one theorem); `body_assign_index`
    skips `:=` inside binders and let/have type binders (same hole
    class as the skeleton seed, 2026-07-19)."""
    from ...state.assemble import body_assign_index
    idx = body_assign_index(text, 0)
    return text[idx + 2:] if idx >= 0 else ""


def _normalize_ws(s: str) -> str:
    """Collapse all runs of whitespace to a single space + strip. Used to
    compare the bridge's `theorem main` signature against the original
    root statement modulo formatting (newlines, indentation, alignment)."""
    return " ".join(s.split())


def check_root_rederivation(
    bridge_path: Path, *, statement: str, fq_name: str, module: str,
    whitelist: list[str], workspace: Path | None = None,
    token_budget: int = _REDERIVATION_TOKEN_BUDGET,
    prober=None,
) -> GateResult:
    """Gate B: the original root must be re-derivable from the Library in
    one short step (plan §2, the 定海神針).

    `bridge_path` is the candidate re-derivation file — a Defs-free
    `Root.lean` of the shape `import Library.…; theorem main : <stmt> :=
    <one-line>`. `statement` is the ORIGINAL root's statement (verbatim
    from `goals.statement`); the bridge MUST prove exactly it. `fq_name`
    / `module` name the theorem + its module for `axiom_probe`.

    Four checks, all hard except the token-budget soft signal:
      0. statement-pin — the bridge's `theorem main : <sig> :=` signature
         equals the original statement (modulo whitespace). WITHOUT this,
         a bridge `theorem main : True := trivial` passes import-closure,
         builds, has clean axioms, and is one line — silently "proving"
         the wrong theorem and defeating the entire gate. The agent has
         filesystem edit access to the Library dir (it may need to fix a
         mis-stated Library lemma), so it CAN clobber the signature; this
         re-checks rather than trusting framework skeleton generation.
      1. import-closure — the bridge imports only Mathlib/Library (Gate A).
      2. axiom_probe — the bridge builds AND `main`'s axiom set ⊆ whitelist
         (reuses pipeline/_axiom.axiom_probe — one warm-gateway shot).
      3. soft: the proof body is short (a long body ⇒ Library missing a
         keystone; reported as an issue but the build/axiom gates are the
         authority).

    `prober` overrides the axiom_probe callable (signature
    `(workspace, *, fq_name, module, whitelist) -> (ok, msg)`) — for tests
    that must not hit a live gateway. Defaults to the real probe.
    """
    issues: list[str] = []

    if not bridge_path.exists():
        return GateResult(False, [f"{bridge_path}: file does not exist"])

    text = bridge_path.read_text(encoding="utf-8", errors="replace")

    # 0. statement-pin — the bridge must prove the original statement, not
    # a weaker/different one. Look for `theorem main : <statement> :=` in
    # the whitespace-normalized file. The needle's `:=` terminator stops a
    # prefix-match (e.g. statement `P` falsely matching `P ∧ Q`).
    needle = f"theorem main : {_normalize_ws(statement)} :="
    if needle not in _normalize_ws(text):
        issues.append(
            f"{bridge_path.name}: bridge does not prove the original root "
            f"statement (expected `theorem main : {_normalize_ws(statement)} "
            f":=`)")

    # 1. import-closure (Defs-free: only Mathlib/Library)
    closure = check_import_closure_text(text, label=bridge_path.name)
    issues.extend(closure.issues)

    # 2. build + axiom_probe (one shot). `prober` is injectable for
    # testing; defaults to the real warm-gateway axiom_probe.
    if prober is None:
        from ...pipeline._axiom import axiom_probe as prober
    ws = workspace or bridge_path.parent
    ok, msg = prober(
        ws, fq_name=fq_name, module=module, whitelist=whitelist)
    if not ok:
        issues.append(f"{bridge_path.name}: re-derivation build/axiom "
                      f"failed — {msg}")

    # 3. soft signal: re-derivation should be a one-liner
    body_tokens = len(_proof_body(text).split())
    if body_tokens > token_budget:
        issues.append(f"{bridge_path.name}: re-derivation proof is long "
                      f"({body_tokens} tokens > {token_budget}) — Library "
                      f"likely missing a keystone (completeness check)")

    return GateResult(not issues, issues)


# ---------------------------------------------------------------------
# Gate D — Defs definition-equivalence (`rfl` defeq), plan §2/§3b
# ---------------------------------------------------------------------
# A migrated `def` is the one thing build + axiom秒殺 cannot guard. A def
# named in the root statement appears in BOTH the theorem's hypotheses
# and its conclusion, so silently changing the def's body (`def IsFoo :=
# True`) changes the meaning of the very theorem Gate B re-derives — the
# bridge then re-derives the WRONG statement and still passes every gate.
# `rfl` is the precise "not tampered" check: `@Problems.p.foo =
# @<target>.foo := rfl` succeeds iff the two are definitionally equal,
# and the kernel transitively unfolds the whole dependency chain (a def
# citing a sibling def is covered as long as the sibling also passes).
#
# def / abbrev only. structure / class / inductive are NOMINAL — two
# separate declarations are never defeq even with identical fields, so
# rfl cannot equate them; the caller decline-and-flags those kinds.


def def_equivalence_probe(defs_fq: str, target_fq: str, *,
                          imports: list[str]) -> str:
    """The throwaway `.lean` that proves the two definitions defeq. It is
    a verification probe, NOT a Library file, so it MAY import the
    problem's `Defs` (the Defs-free north star governs Library files, not
    the prober that checks them). `@` makes every binder explicit so the
    equation is between the bare definition values; a migrate that changed
    the signature makes the `=` itself ill-typed → the probe fails to
    elaborate → tampering caught."""
    import_block = "\n".join(f"import {m}" for m in imports)
    return (f"{import_block}\n"
            f"example : @{defs_fq} = @{target_fq} := rfl\n")


def check_def_equivalence(
    defs_fq: str, target_fq: str, *, imports: list[str],
    verifier=None, workspace: Path | None = None,
) -> GateResult:
    """Gate D: the Defs definition `defs_fq` is definitionally equal to
    its migrated (Library) or cited (mathlib) counterpart `target_fq`.

    Builds `example : @defs_fq = @target_fq := rfl` (importing `imports`,
    which must cover both sides — the problem's Defs plus the Library
    file or Mathlib) and checks it elaborates clean. A clean build IS the
    proof of defeq; `rfl` uses no axioms, so no axiom check is needed.

    `verifier(probe_text) -> (ok, detail)` is injectable so unit tests
    run gateway-free; defaults to the warm-gateway build. Only for
    def/abbrev — nominal kinds (structure/class/inductive) can never be
    rfl-equal across two declarations and must be handled by the caller.
    """
    probe = def_equivalence_probe(defs_fq, target_fq, imports=imports)
    if verifier is None:
        verifier = _warm_defeq_verifier(workspace)
    ok, detail = verifier(probe)
    if ok:
        return GateResult(True, [])
    return GateResult(False, [
        f"def-equivalence failed: `{defs_fq}` is not defeq to "
        f"`{target_fq}` — {detail}"])


def _warm_defeq_verifier(workspace):
    """Default verifier: stage the probe under `Library/` (so Library
    imports resolve) and run one warm-gateway build. Clean build → defeq
    holds. Mirrors librarian._warm_build_verifier's temp-file staging."""
    import os
    import tempfile

    def _verify(probe_text: str) -> tuple[bool, str]:
        from ...lsp import lifecycle as gateway_lifecycle
        ws = workspace or Path(".")
        libdir = ws / "Library"
        libdir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=".lean", prefix="_defeq_probe_",
                                   dir=str(libdir))
        tmp_path = Path(tmp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(probe_text)
            r = gateway_lifecycle.verify_file(
                tmp_path, write_olean=False, workspace=ws)
            if "error" in r and r.get("error"):
                return False, f"verify infra error: {r['error']}"
            if not r.get("ok"):
                errs = "; ".join(
                    d.get("message", "")[:120]
                    for d in (r.get("diagnostics") or [])
                    if d.get("severity") == "error"
                )[:300]
                return False, errs or "(no error diagnostics)"
            return True, ""
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return _verify
