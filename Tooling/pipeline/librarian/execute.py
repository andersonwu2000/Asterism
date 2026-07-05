"""librarian.execute — split out of the former pipeline/librarian.py monolith."""
from __future__ import annotations

import re
import threading
from typing import NamedTuple
from ...state import db, thresholds

from ._base import _MechIntegrityError, _code_normalized, _sorted_import_lines
from .astslice import _decl_signature, _defs_decl_namespace, _defs_decl_source, _library_module_of, _ns_is_operator_specified, extract_decls
from .gate import _warm_olean_writer, migrate_commit_gate, migrate_defeq_gate
from . import schedule
from .schedule import _affected_cone
from .context import compile_librarian_context


def _inject_heartbeat_options(text: str) -> str:
    """Insert elaboration-budget options after the import block (migrate's
    heartbeat rung — see the caller). Idempotent."""
    if "synthInstance.maxHeartbeats" in text:
        return text
    lines = text.splitlines()
    k = max((i + 1 for i, l in enumerate(lines)
             if l.startswith("import ")), default=0)
    lines[k:k] = ["", "set_option maxHeartbeats 800000",
                  "set_option synthInstance.maxHeartbeats 400000"]
    return "\n".join(lines)


class _MechAssembly(NamedTuple):
    """Structured form of a mechanically-assembled migrate file, so per-hole
    fills can swap a single decl's chunk and reassemble WITHOUT re-parsing
    Lean decl boundaries (the chunks are already split per decl). `chunks`
    maps slug → that decl's namespace-body text; `slugs` is the emission order;
    `header` is the hoisted imports (+ opens) block. `chunk_ns` maps slug → the
    namespace block it must be emitted under (default `target_module`); a Defs
    decl the operator authored under an explicit namespace (e.g. `Complex`)
    keeps THAT namespace, so it lands in its own `namespace Complex` block
    rather than the file's Library namespace (see `_defs_decl_namespace`)."""
    header: str
    target_module: str
    slugs: list
    chunks: dict
    chunk_ns: "dict | None" = None


def _reassemble(asm: "_MechAssembly", overrides: "dict | None" = None) -> str:
    """Rebuild the whole-file text from an assembly, optionally replacing some
    slugs' chunks (per-hole fills). `_reassemble(asm)` reproduces the original
    mechanical text exactly — the migrate text and the merge path share this
    one formatter so they can never drift.

    Chunks emit in `asm.slugs` order, grouped into `namespace … end` blocks by
    each chunk's namespace (`asm.chunk_ns`, default `target_module`). Almost
    every chunk uses `target_module` → one block, byte-identical to the old
    single-namespace format. A Defs decl the operator authored under an
    explicit namespace (e.g. `Complex`) carries that namespace, so consecutive
    such chunks form their own `namespace Complex` block — preserving the
    qualified name the root statement cites. Grouping is run-based (consecutive
    same-namespace chunks share a block) so the topological emission order is
    never reordered (a def must precede its users)."""
    chunks = dict(asm.chunks)
    if overrides:
        chunks.update(overrides)
    chunk_ns = asm.chunk_ns or {}
    parts: list[str] = []
    run: list[str] = []
    run_ns: "str | None" = None

    def _flush() -> None:
        if run:
            parts.append(f"namespace {run_ns}\n\n" + "\n\n".join(run)
                         + f"\n\nend {run_ns}")

    for s in asm.slugs:
        ns = chunk_ns.get(s) or asm.target_module
        if ns != run_ns:
            _flush()
            run.clear()
            run_ns = ns
        run.append(chunks[s])
    _flush()
    return asm.header + "\n\n" + "\n\n".join(parts) + "\n"


def _extract_single_decl(text: str, target_module: str) -> "tuple[str, list]":
    """Split a per-decl staging file (the incremental migrate seed:
    `import … + namespace target + ONE decl + end`) into `(decl_chunk,
    extra_imports)`. The decl is alone in the namespace body, so extraction
    is exact — no anchor heuristics. `extra_imports` are the `import` lines
    the agent added (e.g. a Mathlib lemma's module), to fold into the final
    file's header; the self-import of the partial target module is dropped
    by the caller."""
    body: list[str] = []
    imports: list[str] = []
    inside = False
    for ln in text.splitlines():
        if ln.startswith("import "):
            imports.append(ln)
            continue
        if ln.startswith(f"namespace {target_module}"):
            inside = True
            continue
        if ln.startswith(f"end {target_module}"):
            inside = False
            continue
        if inside:
            body.append(ln)
    return "\n".join(body).strip("\n"), imports


def _demote_to_hole(chunk: str, target_module: str) -> "str | None":
    """Turn a mechanically-relabelled decl chunk into a `sorry` hole seed —
    keep its (relabelled, build-clean) signature, drop the body. Used to
    demote a mechanical relabel that breaks the build to a per-decl LLM fill
    instead of an opaque whole-file failure. Returns None if the body
    boundary can't be found (then the caller fails loud)."""
    from ...quality.librarian.relabel import _replace_body_with_sorry
    wrapped = f"namespace {target_module}\n{chunk}\nend {target_module}\n"
    seeded = _replace_body_with_sorry(wrapped, target_module)
    if seeded is None:
        return None
    body, _imports = _extract_single_decl(seeded, target_module)
    return body or None


def _merge_header(header: str, extra_imports: "set[str]") -> str:
    """Fold `extra_imports` into a `_MechAssembly.header` (imports Mathlib-first,
    a blank line, any hoisted `universe`s, a blank line, then `open`s),
    de-duplicating. `universe` lines MUST be carried through — dropping them
    reintroduces the `unknown universe`/`already declared` breakage the merge's
    hoist fixed (they'd survive the 0-hole `_reassemble` path but vanish on the
    seed/stage paths that route through here)."""
    lines = header.splitlines()
    imports = {l for l in lines if l.startswith("import ")}
    universes = [l for l in lines if l.startswith("universe ")]
    opens = [l for l in lines if l.startswith("open ")]
    for e in extra_imports:
        if e.startswith("import "):
            imports.add(e)
        elif e.startswith("open ") and e not in opens:
            opens.append(e)
    out = "\n".join(_sorted_import_lines(imports))
    if universes:
        out += "\n\n" + "\n".join(sorted(set(universes)))
    if opens:
        out += "\n\n" + "\n".join(sorted(set(opens)))
    return out


def _hole_still_unfilled(chunk: str, seed_chunk: str) -> bool:
    """True when an extracted hole chunk was not actually filled — still
    carries a `sorry`, or is byte-identical to the seed stub. A distinct,
    no-sorry failure is the Strategist-escalation hook; a `sorry` must
    never reach the commit gate."""
    if chunk.strip() == seed_chunk.strip():
        return True
    return re.search(r"(^|\W)sorry(\W|$)", chunk) is not None


def _mechanical_migrate_file(
    conn, *, problem, workspace, target_file, target_module, rows,
) -> "tuple[str | None, list[str], _MechAssembly | None]":
    """Best-effort relabel of a whole classified file (librarian_plan §4
    Phase 1) — no LLM. Returns `(assembled_text, holes)`:

      - Every decl relabels cleanly → `(text, [])`: a fully mechanical file
        the caller commits with zero spawn.
      - Some decls decline (body cites a non-keep sibling that can't be
        mechanically redirected) → they are emitted as `<relabelled-sig> :=
        sorry` and their slugs returned in `holes`. The text is then a SEED:
        a real Lean file (sorry only warns) the LLM finishes by filling the
        holes, instead of writing the whole file from scratch (the prior
        ChainAssembly-timeout root cause). All N decls are present and in
        order, so positional pairing still holds.
      - A decl can't even be seeded (no proof file, or its SIGNATURE itself
        cites a non-keep symbol so `body_to_sorry` also declines) → `(None,
        [])`: the caller cold-spawns the whole file. Per the §4 data all
        Jordan holes have clean signatures, so this is the rare path.

    Builds the relabel inputs from DB state:
      - keep_slugs    : every `keep` decl (becomes a Library sibling)
      - defs_imports  : migrated Defs symbol → its Library module
      - citation_map  : verbatim-merge sibling → canonical (full-signature
                        equal only; near-merge / drop / cite-mathlib are NOT
                        here → those decls become holes)
    """
    import re as _re
    from ...quality.librarian import inventory as _inv
    from ...quality.librarian import relabel as _relabel

    all_rows = db.library_decls_for(conn, problem)
    keep_slugs = {r["slug"] for r in all_rows if r["verdict"] == "keep"}
    all_defs = set(_inv.defs_decls(workspace, problem))

    # sibling_modules: keep-slug → its Library module. A cross-file sibling
    # reference needs `import <mod>` + `open <mod>` (different namespace).
    # Only slugs with a known target_file participate; a keep sibling not
    # yet classified has no module → relabel declines that file to LLM.
    sibling_modules: dict[str, str] = {}
    for r in all_rows:
        if r["verdict"] == "keep" and r["target_file"]:
            sibling_modules[r["slug"]] = _library_module_of(r["target_file"])

    # defs_imports: a Defs symbol that has been migrated → its Library module.
    # A CITED Defs symbol (cross-problem redirect: another problem owns the
    # Library copy) maps to the citation's module instead — same import+open
    # treatment, the def just lives in someone else's file.
    defs_imports: dict[str, str] = {}
    for r in all_rows:
        if r["slug"] not in all_defs:
            continue
        if r["lifecycle"] == "migrated" and r["target_file"]:
            defs_imports[r["slug"]] = _library_module_of(r["target_file"])
        elif r["lifecycle"] == "cited" and r["citation"] \
                and r["citation"].startswith("Library."):
            defs_imports[r["slug"]] = r["citation"].rsplit(".", 1)[0]

    # local_defs: Defs symbols classify placed in THIS file — they migrate
    # together with their users, so they land in the same module namespace
    # (bare name visible, no import, no "not yet migrated" decline). Without
    # this, a file holding both a Defs decl and a lemma that uses it can't
    # migrate (classify is free to co-locate them; layout is nondeterministic).
    # `cited` rows are excluded: a redirected (cross-problem) Defs decl still
    # carries this file as its classified target_file, but it is NOT emitted
    # here — treating it as local would skip the import it needs.
    local_defs = {r["slug"] for r in all_rows
                  if r["slug"] in all_defs and r["target_file"] == target_file
                  and r["lifecycle"] != "cited"}

    pns = f"Problems.{problem}"
    problem_dir = db.problem_dir(workspace, problem)
    proofs = problem_dir / "proofs"

    # citation_map: verbatim-merge → canonical sibling. A merge is only safe
    # to rename mechanically when slug and canonical share the SAME callable
    # signature (binders + conclusion), not just the same conclusion: dedup's
    # verbatim compares `goals.statement` (conclusion only), so a `merge` whose
    # canonical takes a different binder list would mis-position call-site args
    # on rename (root cause 1). We re-check the full signature from the proof
    # files here; any mismatch / missing file declines that decl to the LLM.
    def _full_sig(slug):
        p = _inv.resolve_ci(proofs, f"L_{slug}.lean")   # L_/l_ case-insensitive
        if p is None:
            return None
        return _decl_signature(p.read_text(encoding="utf-8"))
    citation_map: dict[str, str] = {}
    for r in all_rows:
        if r["verdict"] == "merge" and r["citation"]:
            sig1, sig2 = _full_sig(r["slug"]), _full_sig(r["citation"])
            if sig1 and sig2 and sig1 == sig2:
                citation_map[r["slug"]] = r["citation"]
    alias_re = _re.compile(
        r"def\s+\w+\s*:=\s*@?Problems\.[\w.]+\.(s\d+)")

    # strategy_aliases: `sN` → the kept sibling slug whose proof IS that
    # strategy term (the lemma is `def <slug> := @sN`). Lets relabel redirect a
    # NESTED strategy reference (a strategy body that cites another strategy's
    # raw proof-term instead of the lemma name) to the kept sibling lemma.
    strategy_aliases: dict[str, str] = {}
    for r in all_rows:
        if r["verdict"] == "keep" and r["target_file"]:
            ap = _inv.resolve_ci(proofs, f"L_{r['slug']}.lean")
            if ap is not None:
                am = alias_re.search(ap.read_text(encoding="utf-8",
                                                  errors="replace"))
                if am:
                    strategy_aliases[am.group(1)] = r["slug"]

    defs_text = ""
    defs_lean = problem_dir / "Defs.lean"
    if defs_lean.exists():
        defs_text = defs_lean.read_text(encoding="utf-8")

    # Foreign namespaces the problem declares its OWN decls under — e.g.
    # residue_thm puts `windingNumber`/`residue` under `namespace Complex`, so
    # the root statement cites `Complex.windingNumber`. Such an operator-chosen
    # namespace is LOAD-BEARING and is PRESERVED on migration: the decl keeps
    # its `Complex.…` qualified name (its chunk lands in its own `namespace
    # Complex` block, see `chunk_ns` below) so Gate B can still re-derive the
    # original statement, and the name stays mathlib-idiomatic. Only the
    # framework's `Problems.<p>` scaffolding is relabelled to the Library
    # namespace (it must never leak into the self-sufficient Library). Retained
    # as a relabel arg for API parity; the preserve decision is per-decl via
    # `_defs_decl_namespace` + `_ns_is_operator_specified`.
    self_namespaces = {
        m.group(1) for m in re.finditer(
            r"(?m)^namespace\s+([\w.]+)\s*$", defs_text)
        if m.group(1) != pns and not m.group(1).startswith("Problems.")}

    import_set: set[str] = set()
    # Replay Defs.lean's own `import Library.*` lines. relabel drops every
    # decl's `import Problems.<p>.Defs` (by design), and the existing
    # compensation (`defs_imports`) only re-adds modules for symbols DECLARED
    # in this problem's Defs.lean. Under clean-before-cite a Defs.lean can be
    # a pure re-export shim — `import Library.X` + `open …`, zero own decls —
    # so the proofs reached Library symbols transitively through the dropped
    # import and nothing put the Library imports back: opens survived,
    # imports vanished → `unknown namespace` (stokes bdry_chart_topo,
    # 2026-06-11). A redundant import is build-harmless; decide minimizes
    # the block later.
    for ln in defs_text.splitlines():
        if re.match(r"import\s+Library\.", ln.strip()):
            import_set.add(ln.strip())
    open_set: set[str] = set()
    # `universe u` declarations, hoisted + dedup'd like imports/opens. A
    # universe-polymorphic def's source declares `universe u`; merging N such
    # decls into one file replays N identical `universe u` lines → `a universe
    # level named 'u' has already been declared` (librarian_migrate_build_
    # failed, mayer_vietoris 2026-07-03). Unlike set_option/attribute (re-
    # declaring is a harmless no-op), a repeated `universe` is a hard build
    # error, so it MUST be deduped. Hoisted to the header (before namespace)
    # since a universe must be declared before use.
    universe_set: set[str] = set()
    chunk_by_slug: dict[str, str] = {}
    # slug → namespace block it must emit under. Populated only for Defs decls
    # the operator authored under an explicit (non-scaffolding) namespace, which
    # is preserved; every other slug defaults to `target_module` in _reassemble.
    chunk_ns_map: dict[str, str] = {}
    holes: list[str] = []
    # Syntactic oracle over Defs.lean (declInfo RPC): built LAZILY on the
    # first Defs-decl row — one warm elaborate per migrated file that
    # actually slices Defs, none for pure proof files. None (gateway down /
    # stale binary) → the astslice regex fallback, i.e. today's behavior.
    defs_oracle = None
    defs_oracle_tried = False
    for r in rows:
        slug = r["slug"]
        # Resolve this decl's per-decl source uniformly by kind, so Defs
        # decls and the root theorem migrate through the SAME mechanical
        # path as ordinary lemmas — no special cold from-scratch spawn:
        #   - Defs decl (no source goal)  → its slice of Defs.lean
        #   - any goal (lemma OR root)    → its `lean_path` file
        #                                   (root → Root.lean; lemma →
        #                                    proofs/L_<slug>.lean)
        # A source the DB points at but that is missing is file↔DB drift —
        # raised loud, never masked by from-scratch (CLAUDE.md rule 10).
        strat_text = None
        if r["source_goal_id"] is None:
            if not defs_oracle_tried:
                defs_oracle_tried = True
                from ...lsp.decl_oracle import DeclOracle
                defs_oracle = (DeclOracle.for_file(defs_lean,
                                                   workspace=workspace)
                               if defs_lean.exists() else None)
            defs_slice = _defs_decl_source(defs_text, slug,
                                           oracle=defs_oracle)
            if defs_slice is None:
                raise _MechIntegrityError(
                    f"Defs decl `{slug}` not found in Defs.lean")
            # An operator-chosen namespace (e.g. `Complex`) is preserved: emit
            # this decl under its own namespace block so it keeps its qualified
            # name. The chunk body is namespace-agnostic (relabel still wraps it
            # in target_module, which the chunk-split strips), so we only need to
            # tag the destination block.
            _enc_ns = _defs_decl_namespace(defs_text, slug,
                                           oracle=defs_oracle)
            if _ns_is_operator_specified(_enc_ns, problem):
                chunk_ns_map[slug] = _enc_ns
            # Preserve Defs.lean's import/open header so any notation the
            # decl relies on still resolves after migration (relabel drops
            # the Problems imports as usual); ensure the Mathlib umbrella.
            # File-level header only: an `open X in` is decl-scoped and travels
            # in the decl's own slice (`_defs_decl_source`), so exclude it here
            # — hoisting it would dangle a scoped-open above `namespace`.
            hdr = "\n".join(
                ln for ln in defs_text.splitlines()
                if ln.startswith("import ")
                or (ln.startswith("open ") and not re.search(r"\bin\b\s*$", ln)))
            if "import Mathlib" not in hdr:
                hdr = ("import Mathlib\n" + hdr) if hdr else "import Mathlib"
            src = f"{hdr}\nnamespace {pns}\n{defs_slice}\nend {pns}\n"
        else:
            g = db.get_goal(conn, r["source_goal_id"])
            # L_/l_ case-insensitive: resolve the proof file's basename within
            # its dir (DB lean_path is uppercase L_; disk may be lowercase l_).
            src_path = None
            if g:
                _lp = workspace / g["lean_path"]
                src_path = _inv.resolve_ci(_lp.parent, _lp.name)
            if src_path is None:
                raise _MechIntegrityError(
                    f"`{slug}`: proof source "
                    f"{g['lean_path'] if g else '?'} missing (file↔DB drift)")
            src = src_path.read_text(encoding="utf-8")
            m = alias_re.search(src)
            if m:
                strat_name = f"_strategy_{m.group(1)}.lean"
                strat_path = _inv.resolve_ci(proofs, strat_name)
                if strat_path is None:
                    raise _MechIntegrityError(
                        f"`{slug}`: alias → missing {strat_name} "
                        "(file↔DB drift)")
                strat_text = strat_path.read_text(encoding="utf-8")
        kw = dict(problem_namespace=pns, target_namespace=target_module,
                  keep_slugs=keep_slugs, defs_imports=defs_imports,
                  # Exclude this decl's own name: a Defs decl's source contains
                  # its own name (`def <slug>`), which must not be mistaken for
                  # a dependency on an unmigrated Defs symbol. No-op for lemmas
                  # / root (their slug isn't a Defs decl).
                  all_defs_syms=all_defs - {slug}, local_defs=local_defs,
                  citation_map=citation_map,
                  sibling_modules=sibling_modules,
                  strategy_aliases=strategy_aliases,
                  self_namespaces=self_namespaces)

        def _relabel_one(body_to_sorry: bool, best_effort: bool = False):
            if strat_text is not None:
                return _relabel.inline_alias(
                    src, strat_text, slug=slug, body_to_sorry=body_to_sorry,
                    best_effort=best_effort, **kw)
            return _relabel.relabel_self_contained(
                src, body_to_sorry=body_to_sorry, best_effort=best_effort,
                **kw)

        res = _relabel_one(body_to_sorry=False)
        if not res.ok:
            # Body cites a non-keep sibling → seed a body hole (sig clean).
            res = _relabel_one(body_to_sorry=True)
            if res.ok:
                holes.append(slug)
            else:
                # The SIGNATURE itself isn't Defs-free → seed a SIGNATURE
                # hole (best-effort: leave the unresolved ref, body = sorry)
                # for the per-hole LLM to restate Defs-free. Only a
                # structural fault (no namespace / broken alias) fails even
                # this — that is drift, raised loud.
                res = _relabel_one(body_to_sorry=True, best_effort=True)
                if not res.ok:
                    raise _MechIntegrityError(
                        f"`{slug}`: cannot relabel even best-effort "
                        f"({res.reason})")
                holes.append(slug)
        # Split into imports + open lines + the namespace body, to merge
        # all decls into one file (imports + opens hoisted, dedup'd).
        inside = False
        body: list[str] = []
        for ln in res.text.splitlines():
            if ln.startswith("import "):
                import_set.add(ln)
                continue
            # Hoist `universe` wherever it sits (file-level OR pulled inside the
            # namespace by relabel) — checked before the `inside` gate so it is
            # deduped into the header, not replayed per-chunk inside a body.
            if ln.startswith("universe "):
                universe_set.add(ln.strip())
                continue
            # Hoist FILE-LEVEL opens only; an `open X in` is decl-scoped — leave
            # it in the body (inside the namespace, before the decl it scopes)
            # rather than dangling it above `namespace`.
            if ln.startswith("open ") and not re.search(r"\bin\b\s*$", ln):
                open_set.add(ln)
                continue
            if ln.startswith(f"namespace {target_module}"):
                inside = True
                continue
            if ln.startswith(f"end {target_module}"):
                inside = False
                continue
            if inside:
                body.append(ln)
        chunk_by_slug[slug] = "\n".join(body).strip("\n")

    # Fold in the file-level cross-file dependency imports from the
    # authoritative file_dependency_graph. relabel only emits a sibling
    # `import` when the source carried an explicit `import …proofs.L_<sub>`;
    # a citation that reaches a sibling transitively (or bundled inside a
    # `_strategy_*` file) is missed, so its full-qualified reference relabels
    # cleanly but lands in a header with no import for that module → Unknown
    # identifier. The dependency graph knows the edge regardless (it drives
    # the migrate order), so the header must carry it. This covers all three
    # consumers of `header` — the 0-hole mechanical commit, the incremental
    # per-decl staging (`_stage`), and the final assembled file. The graph is
    # a DAG over already-classified files and we only import upstream deps, so
    # no cycle; a redundant import is build-harmless.
    dep_imports = {
        f"import {_library_module_of(df)}"
        for df in schedule.file_dependency_graph(
            conn, problem=problem, workspace=workspace).get(target_file, set())}
    import_set |= dep_imports
    # Dedupe repeated `variable` blocks across chunks: each Defs slice replays
    # its own in-scope variables (8bffdcb), so N defs from one section emit N
    # identical blocks. Build-harmless (re-declaring identical variables is a
    # no-op) but ugly Library text. Keep the FIRST occurrence of each distinct
    # block; later byte-identical leading blocks are stripped from their chunk.
    seen_var_blocks: set[str] = set()
    for r in rows:
        chunk = chunk_by_slug.get(r["slug"])
        if chunk is None:
            continue
        lines, k, kept = chunk.splitlines(), 0, []
        while k < len(lines):
            if not lines[k].strip():
                kept.append(lines[k]); k += 1
                continue
            if re.match(r"variable\b", lines[k].strip()):
                j = k + 1
                while j < len(lines) and lines[j][:1] in (" ", "\t"):
                    j += 1
                block = "\n".join(lines[k:j])
                if block not in seen_var_blocks:
                    seen_var_blocks.add(block)
                    kept.extend(lines[k:j])
                k = j
                continue
            break                                  # first real content line
        kept.extend(lines[k:])
        chunk_by_slug[r["slug"]] = "\n".join(kept).strip("\n")
    header = "\n".join(_sorted_import_lines(import_set))   # Mathlib-first (#42)
    if universe_set:                                       # after imports, before opens/decls
        header += "\n\n" + "\n".join(sorted(universe_set))
    if open_set:
        header += "\n\n" + "\n".join(sorted(open_set))
    asm = _MechAssembly(header=header, target_module=target_module,
                        slugs=[r["slug"] for r in rows], chunks=chunk_by_slug,
                        chunk_ns=chunk_ns_map)
    return _reassemble(asm), holes, asm


def _commit_migrated_file(
    patch_text, *, conn, problem, workspace, target_path, target_module,
    ordered_slugs, defs_names, whitelist,
    probe_verifier=None, defeq_verifier=None,
    olean_writer=None):
    """Validate a whole-file migrate candidate and, on success, commit it
    (write the file + mark every decl migrated). Shared by the 0-hole
    mechanical fast path and the incremental per-decl assembly, so the commit
    contract (Gate A + pairing + Gate D + olean) is single-sourced.

    Returns a PipelineResult. The verifier args are injectable for offline
    tests; production passes None → real warm-gateway probes.
    """
    from .. import PipelineResult

    # Gate A import-closure + one-elaboration build + per-decl axiom check.
    gate = migrate_commit_gate(patch_text, target_path, whitelist=whitelist,
                               workspace=workspace,
                               probe_verifier=probe_verifier)
    if not gate.ok:
        return PipelineResult(outcome="failed",
                              failure_reason="librarian_gate_failed",
                              failure_detail=gate.detail,
                              proposal_md=patch_text)
    # Positional slug ↔ declaration pairing (migrate.md mandates exactly
    # the listed decls, in order). A mismatch breaks target_name backfill
    # and Gate D — fail with a clear, retryable message.
    decls = extract_decls(patch_text)
    if len(decls) != len(ordered_slugs):
        return PipelineResult(
            outcome="failed", failure_reason="librarian_gate_failed",
            failure_detail=(
                f"file declares {len(decls)} top-level declaration(s) "
                f"but {len(ordered_slugs)} were classified into it "
                f"({ordered_slugs}); emit exactly the listed "
                "declarations, in order"),
            proposal_md=patch_text)
    # Stage the whole file: Gate D's rfl probe imports the module, so the
    # target must be on disk. Roll back if any decl's Gate D rejects.
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(patch_text)
    for slug, decl in zip(ordered_slugs, decls):
        dgate = migrate_defeq_gate(
            patch_text, problem=problem, target_slug=slug,
            defs_decls=defs_names, target_module=target_module,
            target_fq=decl.fq_name, kind=decl.kind, workspace=workspace,
            defeq_verifier=defeq_verifier)
        if not dgate.ok:
            try:
                target_path.unlink()
            except OSError:
                pass
            return PipelineResult(
                outcome="failed", failure_reason="librarian_gate_failed",
                failure_detail=f"{slug}: {dgate.detail}",
                proposal_md=patch_text)
    # Persist the committed file's .olean so its importers (dispatched later
    # in topological order) build against a fresh dependency, not a stale one
    # (R1b). Mirrors proof-time's per-lemma write_olean=True.
    ok, detail = (olean_writer or _warm_olean_writer(workspace))(target_path)
    if not ok:
        try:
            target_path.unlink()
        except OSError:
            pass
        return PipelineResult(
            outcome="failed", failure_reason="librarian_gate_failed",
            failure_detail=f"olean write: {detail}", proposal_md=patch_text)
    # All gates passed — advance every decl to 'migrated', backfilling each
    # one's fully-qualified Library name (classify wrote it NULL).
    for slug, decl in zip(ordered_slugs, decls):
        db.mark_library_migrated(conn, problem=problem, slug=slug,
                                 target_name=decl.fq_name)
    return PipelineResult(outcome="success")


def _migrate_file_incremental(
        conn, *, problem, workspace, pipeline_id, target_file,
        target_path, target_module, ordered_slugs, defs_names, whitelist,
        attempts_dir, problem_dir, prompt_path, holes, mech_asm,
        fill_fn=None, olean_writer=None, localize=False):
    """migrate Phase 2 (#87) — incremental, per-declaration. Build the target
    file declaration-by-declaration in file_order: a mechanically-relabelled
    decl is appended directly; a decl that needs the LLM is staged ALONE —
    `import <the target module built so far> + the one decl seed` — filled by
    its own small spawn and BUILT against the prior decls before it joins the
    file. So every decl is build-verified the moment it lands (mirroring the
    proof phase's per-lemma topological build), the LLM never synthesises more
    than one declaration (no whole-file over-think), and there is no
    from-scratch path.

    Sequential within the file (each spawn is tiny → no over-think); files
    migrate in parallel at the dispatcher level (`dispatch.pool`), so no nested
    pool is needed. A decl that can't be filled → distinct no-`sorry` failure
    (`librarian_migrate_hole_unfilled`, the Strategist-escalation hook); a
    `-- decline: needs-upstream` routes through the shared cascade. `fill_fn` /
    `olean_writer` are injectable for offline tests.
    """
    from .. import PipelineResult
    from .._retry import SpawnCtx, run_lsp_edit_loop
    from ...core import dispatcher

    holes_set = set(holes)
    olw = olean_writer or _warm_olean_writer(workspace)
    # migrate.md is the per-decl prompt (rewritten for this scope; there is no
    # separate migrate_hole.md).
    hole_prompt = prompt_path
    target_existed = target_path.exists()
    # mech is rebound when a mechanical relabel is demoted to a hole, so the
    # nested helpers read the latest chunks.
    mech = mech_asm

    def _drop_partial():
        # The target file is CREATED by this migrate; remove a partial staging
        # write on failure (don't touch a pre-existing file — there shouldn't
        # be one).
        if not target_existed and target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                pass

    def _stage(subset) -> "tuple[bool, str]":
        # Write the decls done so far (a slug subset, from `done`) to the real
        # target + build its olean, so a following decl can `import` them
        # (R1b per-file olean).
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            _reassemble(mech._replace(slugs=list(subset)), overrides=done),
            encoding="utf-8")
        return olw(target_path)

    def _default_fill_decl(slug):
        """Stage `import <partial target> + the one decl seed`, spawn one
        agent to finish that single declaration, build-verify, and return
        `((chunk, extra_imports), None)`. Returns `(None, decline_text)` on a
        `-- decline:`, `(None, None)` on exhaustion."""
        dattempts = attempts_dir / f"decl-{slug}"
        dattempts.mkdir(parents=True, exist_ok=True)
        patch = dattempts / "patch.lean"
        dpid = f"{pipeline_id}:decl-{slug}"
        # Seed the LLM with the SAME header the assembled file will have
        # (`mech.header`: every cross-file sibling + Defs import AND its `open`,
        # added by relabel) plus a self-`import` of the partial target so prior
        # decls are in scope. This way the fill's compile environment == the
        # final file's: bare sibling / Defs names resolve exactly as they will
        # after assembly (no `?m` autobind from a missing Defs `open`).
        seed_header = _merge_header(mech.header, {f"import {target_module}"})
        seed = (seed_header
                + f"\n\nnamespace {target_module}\n\n"
                + mech.chunks[slug]
                + f"\n\nend {target_module}\n")
        cap: dict = {}

        def cold_prep(ctx: SpawnCtx) -> None:
            compile_librarian_context(
                conn, problem=problem, work_kind="migrate",
                attempts_dir=ctx.attempts_dir, workspace=workspace,
                target_file=target_file, holes=holes, solo_hole=slug)
            patch.write_text(seed, encoding="utf-8")

        def parse() -> PipelineResult:
            if not patch.exists():
                return PipelineResult(
                    outcome="failed", failure_reason="agent_no_output",
                    failure_detail=f"decl {slug}: no patch.lean")
            text = patch.read_text(encoding="utf-8")
            if "-- decline:" in text:
                cap["decline"] = text
                return PipelineResult(
                    outcome="agent_declined", failure_reason="agent_declined",
                    failure_detail=(f"decl {slug} declined: {d}"
                                    if (d := _decline_summary(text))
                                    else f"decl {slug} declined"),
                    proposal_md=text)
            chunk, imports = _extract_single_decl(text, target_module)
            if not chunk:
                return PipelineResult(
                    outcome="failed", failure_reason="librarian_gate_failed",
                    failure_detail=f"decl {slug}: no declaration in the "
                                   f"`{target_module}` namespace",
                    proposal_md=text)
            if _hole_still_unfilled(chunk, mech.chunks[slug]):
                return PipelineResult(
                    outcome="failed",
                    failure_reason="librarian_migrate_hole_unfilled",
                    failure_detail=f"decl {slug}: still `sorry` after fill",
                    proposal_md=text)
            # Keep only genuinely new imports the agent added; drop the seed's
            # own (mech.header's siblings/Defs + Mathlib + the partial-target
            # self-import, which must never appear in the committed file —
            # mech.header already carries the real ones).
            seed_imports = {l for l in seed_header.splitlines()
                            if l.startswith("import ")}
            cap["chunk"] = chunk
            cap["imports"] = [im for im in imports if im not in seed_imports]
            return PipelineResult(outcome="success")

        # `release_session_after=True`: a tight per-decl loop must free the
        # gateway slot before the next decl registers, or the pool exhausts.
        res = run_lsp_edit_loop(
            conn=conn, goal_id=None, pipeline_id=dpid,
            budget_threshold=thresholds.BUILDER_THRESHOLD,
            shelve_threshold=thresholds.SHELVE_THRESHOLD,
            attempts_dir=dattempts, workspace=workspace,
            problem=problem, problem_dir=problem_dir,
            kind="librarian", prompt_path=hole_prompt, target=patch,
            cold_prep_fn=cold_prep, parse_fn=parse,
            release_session_after=True)
        if res.outcome == "success":
            return (cap["chunk"], cap["imports"]), None
        return None, cap.get("decline")

    fill = fill_fn or _default_fill_decl
    done: dict[str, str] = {}        # slug -> final namespace-body chunk
    extra_imports: set[str] = set()

    def _d(detail) -> str:
        return (detail or "")[:120].encode("ascii", "replace").decode("ascii")

    for i, slug in enumerate(ordered_slugs):
        needs_llm = slug in holes_set
        if not needs_llm:
            done[slug] = mech.chunks[slug]
            if not localize:
                continue                         # trust the final whole build
            # localize mode (entered when the 0-hole whole-file build failed):
            # build through THIS decl; if its mechanical relabel breaks the
            # build, demote it to a hole and fill it per-decl below.
            ok, detail = _stage(ordered_slugs[:i + 1])
            if ok:
                continue
            seed = _demote_to_hole(mech.chunks[slug], target_module)
            if seed is None:
                _drop_partial()
                return PipelineResult(
                    outcome="failed",
                    failure_reason="librarian_integrity_error",
                    failure_detail=f"{slug}: relabel breaks the build and "
                                   f"cannot be demoted ({_d(detail)})")
            mech = mech._replace(chunks={**mech.chunks, slug: seed})
            del done[slug]
            print(f"[librarian] {target_file}: mechanical `{slug}` broke the "
                  "build; demoting to a per-decl LLM fill", flush=True)
            needs_llm = True
        # LLM decl (an original hole or a just-demoted mechanical one): expose
        # the prior decls via a compiled partial target, then fill + build it.
        ok, detail = _stage(ordered_slugs[:i])
        if not ok:
            _drop_partial()
            return PipelineResult(
                outcome="failed", failure_reason="librarian_integrity_error",
                failure_detail=f"{slug}: prior decls do not build ({_d(detail)})")
        filled, decline = fill(slug)
        if decline:
            _drop_partial()
            return _decline_or_reopen(
                conn, problem=problem, workspace=workspace,
                patch_text=decline, stage="migrate")
        if filled is None:
            _drop_partial()
            return PipelineResult(
                outcome="failed",
                failure_reason="librarian_migrate_hole_unfilled",
                failure_detail=(
                    f"{target_path.name}: decl `{slug}` could not be filled — "
                    "the proof obligation exceeds migration; escalate to the "
                    "Strategist. No `sorry` is committed."))
        done[slug] = filled[0]
        extra_imports.update(filled[1])

    header = (_merge_header(mech.header, extra_imports)
              if extra_imports else mech.header)
    merged = _reassemble(mech._replace(header=header), overrides=done)
    res = _commit_migrated_file(
        merged, conn=conn, problem=problem, workspace=workspace,
        target_path=target_path, target_module=target_module,
        ordered_slugs=ordered_slugs, defs_names=defs_names,
        whitelist=whitelist, olean_writer=olean_writer)
    if res.outcome != "success":
        _drop_partial()
    return res


def _run_migrate(conn, *, problem, workspace, pipeline_id, target_file,
                 attempts_dir, problem_dir, prompt_path, whitelist=None):
    """migrate (per-file, plan §5 Step 3): build one Library file holding
    that file's classified decls (in file_order). Phase 1 mechanically
    relabels every decl; a 0-hole assembly that builds commits with no spawn.
    Otherwise Phase 2 (`_migrate_file_incremental`) builds the file
    declaration-by-declaration — mechanical decls appended directly, each decl
    that needs the LLM filled by its own small spawn and build-verified before
    it joins. No whole-file from-scratch / over-think path. Gate D rfl-checks
    each migrated `def`; all decls advance to 'migrated' together."""
    from .. import PipelineResult
    from ...quality.librarian import inventory as _inv

    if not target_file:
        return PipelineResult(outcome="failed",
                              failure_reason="librarian_bad_work_kind",
                              failure_detail="migrate requires target_file")
    rows = [r for r in db.library_decls_for(conn, problem)
            if r["target_file"] == target_file
            and r["lifecycle"] == "classified"]
    if not rows:
        return PipelineResult(
            outcome="failed", failure_reason="librarian_not_classified",
            failure_detail=f"{target_file}: no classified decls")
    rows.sort(key=lambda r: (r["file_order"]
                             if r["file_order"] is not None else 0))
    target_path = workspace / target_file
    target_module = _library_module_of(target_file)
    defs_names = _inv.defs_decls(workspace, problem)

    # Cross-problem shared-def REDIRECT (clean-before-cite salvage; user 拍板
    # 2026-06-11): a Defs decl this problem re-declares VERBATIM, which another
    # problem already migrated into the Library, must not be re-emitted — a
    # second copy is a different kernel object, and consumers would split
    # between two incompatible worlds. Cite the Library copy instead: verdict
    # cite-library (terminal 'cited' + citation fqn); the emitting lemmas then
    # import+open its module via the generic defs_imports channel (which reads
    # cited rows' citation), and the proofs keep working because the copies
    # are defeq — the build gate is the final arbiter.
    # 同源 test = whitespace-normalized source equality of the two problems'
    # Defs.lean slices, AND the Library name is unrenamed (leaf == slug) — a
    # renamed Library copy would leave the bare reference unresolved, so it
    # falls through to the ownership guard's loud fail instead.
    my_defs = db.problem_dir(workspace, problem) / "Defs.lean"
    my_defs_text = (my_defs.read_text(encoding="utf-8")
                    if my_defs.exists() else "")
    redirected: list[str] = []
    for r in rows:
        if r["source_goal_id"] is not None:
            continue                              # only Defs decls redirect
        other = conn.execute(
            "SELECT problem, target_name FROM library_decls WHERE slug = ? "
            "AND problem != ? AND lifecycle IN ('migrated', 'cleaned') "
            "AND target_name IS NOT NULL LIMIT 1",
            (r["slug"], problem)).fetchone()
        if other is None or other["target_name"].rsplit(".", 1)[-1] != r["slug"]:
            continue
        theirs_p = db.problem_dir(workspace, other["problem"]) / "Defs.lean"
        if not (my_defs_text and theirs_p.exists()):
            continue
        mine = _defs_decl_source(my_defs_text, r["slug"])
        theirs = _defs_decl_source(
            theirs_p.read_text(encoding="utf-8"), r["slug"])
        # CODE-only comparison: each problem's Defs carries its own docstring
        # wording for the same def (self's lacked one sentence comp/cont had →
        # the verbatim check missed the redirect and self re-emitted a
        # duplicate, live run 2026-06-11). Comments never change the kernel
        # object — strip them before normalizing.
        if not mine or not theirs \
                or _code_normalized(mine) != _code_normalized(theirs):
            continue                              # same name, different def
        db.set_library_verdict(conn, problem=problem, slug=r["slug"],
                               verdict="cite-library",
                               citation=other["target_name"])
        redirected.append(r["slug"])
        print(f"[librarian] {problem}: `{r['slug']}` already in Library as "
              f"{other['target_name']} ({other['problem']}) — citing, not "
              f"re-emitting", flush=True)
    if redirected:
        rows = [r for r in rows if r["slug"] not in redirected]
        if not rows:
            # the whole file was shared defs — nothing left to emit
            return PipelineResult(outcome="success")
    ordered_slugs = [r["slug"] for r in rows]

    # Cross-problem ownership guard: migrate WRITES target_path whole — if
    # another problem's decls already live in this file (definition-tower
    # obligations independently classifying their shared Defs def into the
    # same natural path, stokes form_coord 2026-06-11), committing would
    # silently CLOBBER the owner's decls while its DB rows keep pointing at
    # vanished content. Loud fail; the layout/merge policy for shared files
    # is a design decision, not something to improvise here.
    #
    # TOCTOU: a check at unit START alone is not enough — the dispatcher runs
    # units in a ThreadPoolExecutor, and three same-path units dispatched
    # together all pass the pre-commit check before any commits (observed
    # live: self and comp both committed, last writer clobbered first). The
    # in-flight set serializes same-path units within the daemon (cross-
    # daemon is excluded by the singleton daemon.pid lock); the DB check
    # inside the lock catches an owner that committed earlier.
    def _owned_by_other():
        return conn.execute(
            "SELECT DISTINCT problem FROM library_decls WHERE target_file = ? "
            "AND problem != ? AND lifecycle IN ('migrated', 'cleaned')",
            (target_file, problem)).fetchone()
    with _MIGRATE_PATHS_LOCK:
        racing = target_file in _MIGRATE_PATHS_IN_FLIGHT
        owner = None if racing else _owned_by_other()
        if not racing and owner is None:
            _MIGRATE_PATHS_IN_FLIGHT.add(target_file)
    if racing:
        # Transient, NOT a verdict on this unit: the lock holder needs minutes
        # while the loser's retries land in seconds — counting these toward
        # LIBRARIAN_MAX_CHAIN_RETRIES burned the cap before the winner finished
        # (live, 2026-06-11). `librarian_file_busy` is exempted from the cap.
        return PipelineResult(
            outcome="failed", failure_reason="librarian_file_busy",
            failure_detail=(
                f"{target_file}: another problem's migrate unit is writing "
                f"this file right now — re-enqueued, not counted."))
    if owner is not None:
        return PipelineResult(
            outcome="failed", failure_reason="librarian_file_owned_by_other",
            failure_detail=(
                f"{target_file} already holds migrated decls of "
                f"{owner['problem']} — committing would clobber them. "
                f"Re-classify this problem's decls to a different file, or "
                f"cite the owner's migrated decls instead of re-emitting."))
    try:
        return _run_migrate_locked(
            conn, problem=problem, workspace=workspace,
            target_file=target_file, target_path=target_path,
            target_module=target_module, rows=rows,
            ordered_slugs=ordered_slugs, defs_names=defs_names,
            whitelist=whitelist)
    finally:
        with _MIGRATE_PATHS_LOCK:
            _MIGRATE_PATHS_IN_FLIGHT.discard(target_file)


_MIGRATE_PATHS_LOCK = threading.Lock()
_MIGRATE_PATHS_IN_FLIGHT: "set[str]" = set()


def _run_migrate_locked(conn, *, problem, workspace, target_file, target_path,
                        target_module, rows, ordered_slugs, defs_names,
                        whitelist):
    """The body of `_run_migrate` past the ownership/race guard — runs with
    `target_file` claimed in `_MIGRATE_PATHS_IN_FLIGHT`."""
    from .. import PipelineResult

    # Phase 1 — mechanical relabel pre-pass (librarian_plan §4): best-effort
    # assemble the whole file by pure relabel (no LLM). file↔DB drift raises
    # _MechIntegrityError — surfaced loud, never masked by a from-scratch spawn
    # (CLAUDE.md rule 9 + 10).
    try:
        mech_text, holes, mech_asm = _mechanical_migrate_file(
            conn, problem=problem, workspace=workspace,
            target_file=target_file, target_module=target_module, rows=rows)
    except _MechIntegrityError as e:
        _detail = str(e)[:200].encode("ascii", "replace").decode("ascii")
        return PipelineResult(
            outcome="failed", failure_reason="librarian_integrity_error",
            failure_detail=_detail)

    # v0.3 (plan §3): migrate is MECHANICAL-ONLY — no Phase-2 LLM. With every
    # decl kept (no dedup), every proof-term reference resolves to a kept
    # sibling, so a clean relabel has no holes. A hole — or a 0-hole assembly
    # that does not build — is therefore a mechanical-relabel limitation (e.g.
    # an alias→strategy body that doesn't inline syntactically, or a dropped
    # Defs import a tactic relied on), surfaced as a HARD FAIL for the operator,
    # NOT silently patched by an LLM (which would reintroduce the variance/risk
    # v0.3 removed). `attempts_dir` / `problem_dir` / `prompt_path` are now
    # unused here (kept in the signature for the dormant incremental path).
    if holes:
        return PipelineResult(
            outcome="failed",
            failure_reason="librarian_migrate_not_mechanical",
            failure_detail=(
                f"{target_file}: {len(holes)} decl(s) not mechanically "
                f"relabelable: {holes}. v0.3 migrate is mechanical-only — "
                "needs operator (fix relabel.py, or decide per-decl). "
                "No LLM fallback, no sorry committed."))

    mech_res = _commit_migrated_file(
        mech_text, conn=conn, problem=problem, workspace=workspace,
        target_path=target_path, target_module=target_module,
        ordered_slugs=ordered_slugs, defs_names=defs_names,
        whitelist=whitelist)
    _hb_detail = mech_res.failure_detail or ""
    if mech_res.outcome != "success"             and ("heartbeats" in _hb_detail
                 or "failed to synthesize" in _hb_detail):
        # ("failed to synthesize" included: the gateway's validate detail is
        # truncated BEFORE the `maximum number of heartbeats` tail, so the
        # timeout flavor is indistinguishable from a missing instance at this
        # layer — a genuinely-missing instance just fails the one retry too.)
        # Heartbeat-budget rung: every decl built STANDALONE at proof time,
        # but the merged file elaborates in a richer environment — the Defs
        # opens replay (`open scoped Manifold/Bundle` activates scoped
        # instances the pure-mathlib helpers never had in scope) can push
        # typeclass synthesis past the 20000 default (stokes form_bundle
        # AlternatingMapContDiff, 2026-06-11: standalone green, merged
        # `timeout at typeclass`). Which opens a decl truly needs is not
        # mechanically decidable; granting the merged file a bigger budget
        # is — and self-limiting (only files that need it get the option,
        # and it lands in the Library file where a reviewer can see it).
        mech_text = _inject_heartbeat_options(mech_text)
        mech_res = _commit_migrated_file(
            mech_text, conn=conn, problem=problem, workspace=workspace,
            target_path=target_path, target_module=target_module,
            ordered_slugs=ordered_slugs, defs_names=defs_names,
            whitelist=whitelist)
        if mech_res.outcome == "success":
            print(f"[librarian] {target_file}: migrated mechanically with "
                  f"heartbeat bump ({len(ordered_slugs)} decls, no LLM)",
                  flush=True)
            return mech_res
    if mech_res.outcome == "success":
        print(f"[librarian] {target_file}: migrated mechanically "
              f"({len(ordered_slugs)} decls, no LLM)", flush=True)
        return mech_res
    # Clean relabel that does not build = subtle mechanical bug; commit gate
    # already removed the partial file. Hard-fail + flag (sanitize unicode).
    _detail = (mech_res.failure_detail or "")[:200].encode(
        "ascii", "replace").decode("ascii")
    return PipelineResult(
        outcome="failed", failure_reason="librarian_migrate_build_failed",
        failure_detail=(
            f"{target_file}: mechanical relabel does not build: {_detail}. "
            "v0.3 mechanical-only — needs operator."))


_NEEDS_UPSTREAM_RE = re.compile(
    r"--\s*decline\s*:\s*needs-upstream\s+([A-Za-z_]\w*)\s*(.*)")


def _parse_needs_upstream(text: str) -> "tuple[str, str] | None":
    """Parse a `-- decline: needs-upstream <slug> [reason]` directive →
    (upstream_slug, reason). The Librarian analog of proof-time
    `return_to_parent`: a downstream node signals that a finalized upstream
    Library decl must be reshaped before it can proceed."""
    m = _NEEDS_UPSTREAM_RE.search(text)
    if not m:
        return None
    return m.group(1), m.group(2).strip()


def _reopen_upstream_cascade(conn, *, problem, workspace, upstream_slug,
                             note) -> list:
    """Re-open a finalized upstream decl + its consumer cone (the Librarian
    analog of proof-time `return_to_parent`, but it RESHAPES nodes rather
    than re-decomposing — the dependency topology is kept).

    The named upstream's file and every file transitively importing it
    (`_affected_cone`) revert migrated/cleaned → 'classified'; their on-disk
    Library files + oleans are deleted (file↔DB paired, CLAUDE rule 10) so
    the next derive re-migrates the faithful baseline and then re-cleans —
    this time with `note` (what the downstream needed) recorded on the
    upstream so its re-cleanup can reshape DIFFERENTLY (else a faithful
    re-migrate would loop to the same result). Bounding is the dispatcher's
    per-problem fail cap. Returns the reopened target_files."""
    rows = db.library_decls_for(conn, problem)
    up = next((r for r in rows if r["slug"] == upstream_slug
               and r["target_file"]), None)
    if up is None:
        return []
    graph = schedule.file_dependency_graph(conn, problem=problem, workspace=workspace)
    reopened: list = []
    for f in sorted(_affected_cone(graph, {up["target_file"]})):
        n = conn.execute(
            "UPDATE library_decls SET lifecycle='classified', updated_at=? "
            "WHERE problem=? AND target_file=? AND lifecycle IN "
            "('migrated','cleaned')", (db.now(), problem, f)).rowcount
        if not n:
            continue
        reopened.append(f)
        p = workspace / f
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
        mod = _library_module_of(f)
        olean = (workspace / ".lake" / "build" / "lib" / "lean"
                 / (mod.replace(".", "/") + ".olean"))
        if olean.exists():
            try:
                olean.unlink()
            except OSError:
                pass
    if note:
        conn.execute(
            "UPDATE library_decls SET reopen_note=? WHERE problem=? AND slug=?",
            (note, problem, upstream_slug))
    conn.commit()
    return reopened


def _decline_summary(text: str) -> str:
    """The agent's decline reason, surfaced into `failure_detail` so the STALL
    log + dead_attempts are self-explanatory (the reason used to be buried in
    `proposal_md` behind a bare '{stage} declined'). Prefers the
    `-- decline: <reason>` directive; else the first non-blank line. Capped."""
    for line in (text or "").splitlines():
        if "-- decline:" in line:
            return line.split("-- decline:", 1)[1].strip()[:300]
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:300]
    return ""


def _decline_or_reopen(conn, *, problem, workspace, patch_text, stage):
    """Map a Librarian agent decline to a PipelineResult. A
    `needs-upstream <slug>` directive triggers the re-open cascade (reshape
    a finalized upstream + its cone); anything else is a plain decline. The
    dispatcher re-enqueues the failure (bounded), so after a cascade the next
    derive re-migrates the reopened cone."""
    from .. import PipelineResult
    nu = _parse_needs_upstream(patch_text)
    if nu:
        slug, reason = nu
        # Only a finalized (placed → has target_file) upstream can be reshaped.
        # A slug that is unknown, or dropped/cited/merged (no target_file, i.e.
        # it already has a REPLACEMENT and is not a Library decl), can't be
        # reshaped — fail LOUD with the verdict→replacement, instead of letting
        # the cascade silently no-op and the chain stall at the fail cap.
        row = next((r for r in db.library_decls_for(conn, problem)
                    if r["slug"] == slug), None)
        if row is None or not row["target_file"]:
            if row is None:
                why = (f"`{slug}` is not a declaration in this problem "
                       f"(check the slug)")
            else:
                why = (f"`{slug}` is {row['verdict']}→`{row['citation'] or '(none)'}`"
                       f", not a Library decl to reshape — cite the replacement, "
                       f"or this is a wrong dedup verdict (revive `{slug}`)")
            return PipelineResult(
                outcome="failed",
                failure_reason="librarian_needs_upstream_unresolvable",
                failure_detail=f"{stage}: needs-upstream {why}",
                proposal_md=patch_text)
        reopened = _reopen_upstream_cascade(
            conn, problem=problem, workspace=workspace, upstream_slug=slug,
            note=reason or f"reshape needed by {stage}")
        if not reopened:
            return PipelineResult(
                outcome="failed",
                failure_reason="librarian_needs_upstream_unresolvable",
                failure_detail=f"{stage}: needs-upstream `{slug}` matched no "
                               f"finalized (migrated/cleaned) decl to reshape "
                               f"(already classified / in-flight?)",
                proposal_md=patch_text)
        return PipelineResult(
            outcome="failed", failure_reason="librarian_reopened_upstream",
            failure_detail=f"{stage}: reopened upstream `{slug}` + cone "
                           f"{reopened}", proposal_md=patch_text)
    return PipelineResult(
        outcome="failed", failure_reason="agent_declined",
        failure_detail=(f"{stage} declined: {d}"
                        if (d := _decline_summary(patch_text))
                        else f"{stage} declined"),
        proposal_md=patch_text)
