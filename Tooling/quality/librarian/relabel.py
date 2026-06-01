"""Mechanical migrate — Phase 1 relabel (librarian_plan §4).

Pure, offline, no gateway / no LLM. Turns an original `Problems/<p>/proofs/
L_<slug>.lean` into a Library-shaped declaration **by relabelling only** —
the framework never reads the proof's meaning, it only renames.

Conservative by design: this module handles the cases it can prove correct
mechanically and returns `RelabelResult(ok=False, ...)` for everything else,
so the caller falls back to the LLM path (Phase 2). The build gate is the
final arbiter — a relabel that compiles is correct; one that doesn't drops
to Phase 2 (librarian_plan §4: "靜態分析會漏，build 不會漏").

What Phase-1 relabel does (and only this):
  1. namespace `Problems.<p>` → the decl's target `Library.<Topic>` namespace
  2. drop `import Problems.<p>.Defs` (+ any Problems-proofs imports)
  3. inline an alias body (`def <slug> := @<ns>.<strategy>`) — DEFERRED,
     see `_is_alias`; for now alias decls decline to Phase 2
  4. rewrite references to non-keep siblings via the dedup citation table
     — DEFERRED (substring-rewrite risk); for now any non-keep reference
     declines to Phase 2

This first cut intentionally only ships case (1)+(2) for self-contained
`keep` decls whose proof closure is a single file with no Problems-sibling
import and no non-keep reference. That is the 50/81 "clean closure" set
(librarian_plan §4 量化證據). Alias inlining and citation rewrite are the
next units.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# A Problems proof/Defs import we must drop or redirect.
_PROBLEMS_IMPORT_RE = re.compile(
    r"^\s*import\s+(Problems\.[\w.]+)\s*$")
# `namespace <ns>` / `end <ns>` lines.
_NS_RE = re.compile(r"^(\s*)namespace\s+([A-Za-z_][\w.]*)\s*$")
_END_RE = re.compile(r"^(\s*)end\s+([A-Za-z_][\w.]*)\s*$")
# An alias decl: `def <name> := @<fq>` (the strategy-indirection form).
_ALIAS_RE = re.compile(
    r"^\s*def\s+\w+\s*:=\s*@?(Problems\.[\w.]+)\s*$", re.MULTILINE)


@dataclass
class RelabelResult:
    """ok=True → `text` is the Library declaration, ready for the commit
    gate. ok=False → `reason` says why this decl can't be relabelled
    mechanically; caller routes it to the Phase-2 LLM path."""
    ok: bool
    text: str = ""
    reason: str = ""


# Imported sub-lemma proof module: `import <PNS>.proofs.L_<sub>` or a
# `_strategy_s<NNNN>` module.
_PROOF_IMPORT_RE = re.compile(
    r"^\s*import\s+(Problems\.[\w.]+)\.proofs\.([A-Za-z_]\w*)\s*$")


def _alias_target(source_text: str) -> "str | None":
    """If the file is an alias `def <name> := @<PNS>.<strategy>`, return the
    bare strategy decl name (`s11000`); else None."""
    m = _ALIAS_RE.search(source_text)
    if not m:
        return None
    fq = m.group(1)            # e.g. Problems.…​.s11000
    return fq.rsplit(".", 1)[-1]


def relabel_self_contained(
    source_text: str, *, problem_namespace: str, target_namespace: str,
    keep_slugs: "set[str] | None" = None,
    rename_decl: "tuple[str, str] | None" = None,
    defs_imports: "dict[str, str] | None" = None,
    all_defs_syms: "set[str] | None" = None,
    citation_map: "dict[str, str] | None" = None,
) -> RelabelResult:
    """Mechanically relabel a single proof file.

    `problem_namespace`  e.g. "Problems.LinearAlgebra.jordan_normal_form"
    `target_namespace`   e.g. "Library.LinearAlgebra.JordanForm.KernelChain"
    `keep_slugs`         the problem's `keep` slug set. When given, a
        `Problems.*.proofs.L_<sub>` import is OK iff `<sub>` ∈ keep_slugs
        (it will become a Library sibling). A non-keep sibling import →
        decline (its citation rewrite is the Phase-2 / citation unit).
        When None, ANY proofs-sibling import declines (the stricter
        first-cut behaviour).
    `rename_decl`        `(old, new)` — rename a declaration head, used by
        alias inlining to turn `theorem s11000` into `theorem <slug>`.
    `defs_imports`       map {Defs-symbol → its migrated Library module},
        e.g. {"IsJordanForm": "Library.LinearAlgebra.JordanForm.Defs"}.
        The original `import Problems.*.Defs` is dropped; for each Defs
        symbol the body actually uses, we add the corresponding Library
        import so the now-migrated definition resolves. The bare name
        still resolves because the Defs Library namespace
        (`Library.LinearAlgebra.JordanForm`) is an ancestor of the target
        namespace, so Lean's namespace lookup finds it. A used Defs symbol
        with no entry in this map → decline (it isn't migrated yet).

    Declines (ok=False) when not safely mechanical:
      - alias (`def x := @strategy`) → caller should use `inline_alias`
      - imports a non-keep Problems sibling → citation rewrite (later)
      - uses a Defs symbol not present in `defs_imports`
      - no recognisable namespace
      - residual `Problems.` after relabel

    On success: keeps `import Mathlib`, drops Defs import, re-adds the
    Library Defs import(s) for Defs symbols the body uses, drops keep
    sibling imports (build resolves them via the Library lib), renames the
    namespace + matching end, optionally renames the decl head; body
    otherwise byte-for-byte intact.
    """
    if _ALIAS_RE.search(source_text):
        return RelabelResult(
            False, reason="alias decl (def := @strategy) — use inline_alias")

    defs_imports = defs_imports or {}
    # Which Defs symbols does the body use? Detect over the FULL Defs symbol
    # set (all_defs_syms), not just the migrated ones — else a used-but-
    # unmigrated symbol would slip through with no import and build-fail.
    # Falls back to defs_imports keys when the full set isn't supplied.
    detect_syms = all_defs_syms if all_defs_syms is not None else set(defs_imports)
    used_defs = [sym for sym in detect_syms
                 if re.search(rf"\b{re.escape(sym)}\b", source_text)]

    lines = source_text.splitlines()
    out: list[str] = []
    ns_seen = False
    for ln in lines:
        m_proof = _PROOF_IMPORT_RE.match(ln)
        if m_proof:
            sub_mod = m_proof.group(2)        # L_<sub> or _strategy_s<NNNN>
            if sub_mod.startswith("L_"):
                sub = sub_mod[2:]
                if keep_slugs is not None and sub in keep_slugs:
                    continue  # keep sibling — drop import, resolved via Library
                if citation_map and sub in citation_map:
                    continue  # verbatim-merge → body rename below resolves it
                return RelabelResult(
                    False, reason=f"imports non-keep sibling `{sub_mod}` — "
                                  "no verbatim citation, needs Phase 2")
            # _strategy_* import inside a body we're relabelling: shouldn't
            # appear except in alias files (handled by inline_alias).
            return RelabelResult(
                False, reason=f"imports `{sub_mod}` — strategy indirection")
        m_imp = _PROBLEMS_IMPORT_RE.match(ln)
        if m_imp:
            mod = m_imp.group(1)
            if mod.endswith(".Defs"):
                continue  # drop Defs import
            return RelabelResult(
                False, reason=f"imports Problems `{mod}` — needs Phase 2")
        m_ns = _NS_RE.match(ln)
        if m_ns and m_ns.group(2) == problem_namespace:
            out.append(f"{m_ns.group(1)}namespace {target_namespace}")
            ns_seen = True
            continue
        m_end = _END_RE.match(ln)
        if m_end and m_end.group(2) == problem_namespace:
            out.append(f"{m_end.group(1)}end {target_namespace}")
            continue
        out.append(ln)

    if not ns_seen:
        return RelabelResult(
            False, reason=f"no `namespace {problem_namespace}` found")

    # Re-add the Library Defs import for each Defs symbol the body uses
    # (the original Problems Defs import was dropped above). A used Defs
    # symbol with no migrated Library module → decline.
    if used_defs:
        modules = []
        for sym in used_defs:
            mod = defs_imports.get(sym)
            if not mod:
                return RelabelResult(
                    False, reason=f"uses Defs symbol `{sym}` with no migrated "
                                  "Library module — needs Phase 2")
            if mod not in modules:
                modules.append(mod)
        # Insert the Library Defs imports right after the leading
        # `import Mathlib` (keep import block contiguous at the top).
        insert_at = 0
        for i, ln in enumerate(out):
            if ln.strip() == "import Mathlib":
                insert_at = i + 1
                break
        for j, mod in enumerate(sorted(modules)):
            out.insert(insert_at + j, f"import {mod}")

    text = "\n".join(out)
    if rename_decl is not None:
        old, new = rename_decl
        # Rename only the declaration head `theorem <old>` / `def <old>` —
        # word-boundary so a substring of another identifier is untouched.
        text = re.sub(rf"\b(theorem|lemma|def|abbrev)\s+{re.escape(old)}\b",
                      rf"\1 {new}", text)
    if citation_map:
        # Redirect verbatim-merge sibling references in the body to their
        # canonical name. Word-boundary token rename — safe because a Lean
        # identifier never spans whitespace, so `\b<slug>\b` can't straddle
        # a larger name. Only slugs the caller vetted as verbatim-equal are
        # here; everything else already declined above.
        for src_slug, dst in citation_map.items():
            text = re.sub(rf"\b{re.escape(src_slug)}\b", dst, text)
    if not text.endswith("\n"):
        text += "\n"
    if "Problems." in text:
        return RelabelResult(
            False, reason="residual `Problems.` reference after relabel "
                          "(body cites a problem symbol) — needs Phase 2")
    return RelabelResult(True, text=text)


def inline_alias(
    alias_text: str, strategy_text: str, *, slug: str,
    problem_namespace: str, target_namespace: str,
    keep_slugs: "set[str] | None" = None,
    defs_imports: "dict[str, str] | None" = None,
    all_defs_syms: "set[str] | None" = None,
    citation_map: "dict[str, str] | None" = None,
) -> RelabelResult:
    """Inline an alias `def <slug> := @<PNS>.<strategy>` by relabelling the
    STRATEGY file's theorem and renaming `<strategy>` → `<slug>`.

    The alias file itself carries no proof — the real declaration lives in
    `_strategy_s<NNNN>.lean`. We relabel that strategy file as a normal
    (now sibling-aware) self-contained file, renaming its `theorem s<NNNN>`
    head to the canonical `<slug>`. Declines for the same reasons as
    `relabel_self_contained` (notably a non-keep sibling import in the
    strategy's closure → citation rewrite unit)."""
    strat = _alias_target(alias_text)
    if strat is None:
        return RelabelResult(False, reason="not an alias decl")
    return relabel_self_contained(
        strategy_text, problem_namespace=problem_namespace,
        target_namespace=target_namespace, keep_slugs=keep_slugs,
        rename_decl=(strat, slug), defs_imports=defs_imports,
        all_defs_syms=all_defs_syms, citation_map=citation_map)
