"""librarian.bridge — split out of the former pipeline/librarian.py monolith."""
from __future__ import annotations

from pathlib import Path as _Path
from ...state import db

from ._base import _import_sort_key
from .astslice import _library_module_of
from .schedule import _harvested_decls


# ---------------------------------------------------------------------
# Stage E — finish (terminal, agentless): provenance + chain termination
# ---------------------------------------------------------------------

def _upsert_index_section(index_text: str, problem: str,
                          section_body: str) -> str:
    """Idempotently replace (or append) the `## <problem>` section in
    INDEX.md. A re-run of finish for the same problem rewrites its
    section in place rather than duplicating it. Sections are delimited
    by `## ` headers; the replaced span runs to the next `## ` (or EOF)."""
    header = f"## {problem}"
    lines = index_text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == header:
            start = i
            break
    new_section = f"{header}\n\n{section_body.rstrip()}\n"
    if start is None:
        base = index_text.rstrip()
        prefix = (base + "\n\n") if base else _INDEX_PREAMBLE
        return prefix + new_section
    # Find end of this section (next top-level `## ` or EOF).
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    before = "\n".join(lines[:start]).rstrip()
    after = "\n".join(lines[end:]).strip()
    out = (before + "\n\n" if before else _INDEX_PREAMBLE) + new_section
    if after:
        out += "\n" + after + "\n"
    return out


def _drop_index_section(index_text: str, problem: str) -> str:
    """Remove the `## <problem>` section from INDEX.md (inverse of
    `_upsert_index_section`) — returns the text unchanged if the section is
    absent. Used to invalidate a stale INDEX entry when an already-promoted
    problem is re-cleaned, so the terminal bridge/Gate B re-fires + re-promotes
    on the rewritten Library (the section span runs to the next `## ` or EOF,
    same delimiting as the upsert)."""
    header = f"## {problem}"
    lines = index_text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip() == header), None)
    if start is None:
        return index_text
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    before = "\n".join(lines[:start]).rstrip()
    after = "\n".join(lines[end:]).strip()
    parts = [p for p in (before, after) if p]
    return ("\n\n".join(parts) + "\n") if parts else ""


_INDEX_PREAMBLE = (
    "# Library Index\n\n"
    "Provenance of declarations harvested from proved Problems, by "
    "source problem. Written by the Librarian `bridge` step.\n\n"
)


def _write_library_index(conn, *, problem, workspace, gate_b_line: str):
    """Write/refresh the `## <problem>` section of `Library/INDEX.md`:
    migrated-decl provenance + the Gate B status line. INDEX presence is the
    chain's idempotent done-marker (`_derive_librarian_work`). Written by the
    bridge step on Gate B PASS."""
    migrated = _harvested_decls(conn, problem)
    lines = [f"_Harvested {db.now()} — {len(migrated)} declaration(s)._", ""]
    for r in migrated:
        name = r["target_name"] or r["slug"]
        lines.append(f"- `{name}` → `{r['target_file'] or '?'}`")
    lines.append("")
    lines.append(gate_b_line)
    index = workspace / "Library" / "INDEX.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    existing = (index.read_text(encoding="utf-8", errors="replace")
                if index.exists() else "")
    index.write_text(
        _upsert_index_section(existing, problem, "\n".join(lines)),
        encoding="utf-8")


def _rederivation_prober(bridge_path):
    """A `check_root_rederivation` prober bound to an already-staged bridge
    file: build it via the warm gateway and report whether `fq_name`'s axiom
    set ⊆ whitelist. Used instead of the default `axiom_probe` (which
    resolves a module to a committed source path) because the bridge is a
    THROWAWAY probe — verify_file compiles the staged temp file directly,
    the same staging `_warm_probe_verifier` uses for migrate candidates."""
    def _probe(ws, *, fq_name, module, whitelist):
        from ...lsp import lifecycle as gw
        r = gw.verify_file(bridge_path, write_olean=False,
                           axioms_for=fq_name, workspace=ws)
        if r.get("error"):
            return False, f"verify infra error: {r['error']}"
        if not r.get("ok"):
            errs = "; ".join(
                d.get("message", "")[:120]
                for d in (r.get("diagnostics") or [])
                if d.get("severity") == "error")[:300]
            return False, errs or "(no error diagnostics)"
        if r.get("axiom_error"):
            return False, f"axiom probe error: {r['axiom_error']}"
        rogue = set(r.get("axioms") or []) - set(whitelist)
        if rogue:
            return False, f"rogue axioms: {sorted(rogue)}"
        return True, ""
    return _probe


def _commit_bridge(patch_text, *, conn, problem, workspace, statement,
                   whitelist, prober=None):
    """Gate B commit (plan §2): stage the agent's bridge as a throwaway probe
    under `Library/`, run `check_root_rederivation` (statement-pin + import-
    closure + build + axiom-whitelist), then delete the probe. On pass, write
    INDEX (Gate B PASSED) — the chain done-marker. The bridge file is NEVER
    committed (it is framework-shaped, not mathlib content); any Library lemma
    the agent fixed en route already persists as a real file. `prober` is
    injectable for offline tests."""
    from .. import PipelineResult
    from ...quality.librarian import gates
    import os
    import tempfile

    libdir = workspace / "Library"
    libdir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".lean", prefix="_bridge_probe_",
                               dir=str(libdir))
    tmp_path = _Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(patch_text)
        module = _library_module_of(f"Library/{tmp_path.name}")
        gate = gates.check_root_rederivation(
            tmp_path, statement=statement, fq_name="main", module=module,
            whitelist=whitelist, workspace=workspace,
            prober=prober or _rederivation_prober(tmp_path))
        if not gate.ok:
            return PipelineResult(
                outcome="failed", failure_reason="librarian_gate_failed",
                failure_detail="; ".join(gate.issues)[:400],
                proposal_md=patch_text)
        _write_library_index(
            conn, problem=problem, workspace=workspace,
            gate_b_line="Gate B (root re-derivation): PASSED — original "
                        "`main` re-derived from the Library alone; axioms "
                        "within whitelist.")
        return PipelineResult(outcome="success", proposal_md=patch_text)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _bridge_probe_text(conn, *, problem, statement, migrated,
                       workspace=None) -> "str | None":
    """v0.3 mechanical Gate B probe (plan §2/§3). Build a throwaway Root that
    imports every migrated Library module, opens every migrated namespace (so
    the original statement's bare symbols — e.g. a `Defs` predicate now living
    in the Library — resolve), replays the problem's Defs.lean file-level
    `open` clauses (the statement was AUTHORED under them — without e.g.
    `open scoped Manifold` a statement using `𝓡∂`/`∞` notation doesn't even
    PARSE, and the probe fails as a false `librarian_bridge_not_mechanical`;
    stokes 2026-06-11), and re-derives the original `main` by citing its
    migrated form: `theorem main : <statement> := by exact <main_fq>`. Returns
    None when the migrated root decl has no Library name (cannot build a probe).

    No agent: the migrated `main` IS the original theorem relabelled, so a
    direct citation is the whole derivation. If it does not typecheck, the
    statement needs a non-mechanical bridge (load-bearing Defs / RequestUserAmend)
    — surfaced as a hard fail upstream, not patched by an LLM."""
    root_slug = conn.execute(
        "SELECT slug FROM goals WHERE problem = ? AND origin = 'root' "
        "AND status = 'proved' ORDER BY id LIMIT 1", (problem,)).fetchone()
    root_slug = root_slug["slug"] if root_slug else "main"
    main_row = next((r for r in migrated if r["slug"] == root_slug), None)
    if main_row is None or not main_row["target_name"]:
        return None
    main_fq = main_row["target_name"]
    modules, namespaces = set(), set()
    for r in migrated:
        if r["target_file"]:
            modules.add(_library_module_of(r["target_file"]))
        if r["target_name"] and "." in r["target_name"]:
            namespaces.add(r["target_name"].rsplit(".", 1)[0])
    # CITED decls (cross-problem redirect): the original statement references
    # them bare, but they live in ANOTHER problem's Library module — the probe
    # must import + open that module too or the statement doesn't elaborate.
    # ONLY Library citations: cite-drop also records MATHLIB citations
    # (`Set.mem_of_mem_inter_left`), and naively splitting one yields
    # `import Set` → unknown module prefix → the whole probe is red and Gate B
    # reports a false not_mechanical (stokes_pullback 2026-06-12). A mathlib
    # citation needs nothing here — its consumers were inlined at drop time
    # and the root statement never references it.
    for r in db.library_decls_for(conn, problem):
        if r["lifecycle"] == "cited" and r["citation"] \
                and r["citation"].startswith("Library."):
            ns = r["citation"].rsplit(".", 1)[0]
            modules.add(ns)
            namespaces.add(ns)
    lines = [f"import {m}" for m in sorted(modules, key=_import_sort_key)]  # #42
    lines += [f"open {ns}" for ns in sorted(namespaces)]
    lines += ["", f"theorem main : {statement} := by exact {main_fq}", ""]
    text = "\n".join(lines)
    if workspace is not None:
        # Same replay every proof-file author gets (backward/builder/forward);
        # inserts after the last import, before the opens/theorem.
        from ...state import manifest as _mfst
        text = _mfst.inject_defs_opens(text, problem=problem,
                                       workspace=workspace)
    return text


def _run_bridge(conn, *, problem, workspace, pipeline_id,
                attempts_dir=None, problem_dir=None, prompt_path=None,
                whitelist=None):
    """Gate B step (plan §2 定海神針) — v0.3 MECHANICAL probe, no agent, no LLM.

    Re-derive the original root `theorem main` from the Library alone by citing
    `main`'s migrated form (`_bridge_probe_text`), then `_commit_bridge` stages
    it as a throwaway probe and runs `check_root_rederivation` (statement-pin +
    import-closure + build + axiom-whitelist). On pass writes INDEX (the chain
    done-marker). If the mechanical citation does not typecheck, the
    Library/statement needs a non-mechanical bridge (load-bearing Defs that
    mathlib can't express → RequestUserAmend) — HARD FAIL + flag operator, not a
    silent LLM patch. `attempts_dir`/`problem_dir`/`prompt_path` are unused
    (kept for signature parity with the dispatcher's run_librarian call)."""
    from .. import PipelineResult
    from ...quality.librarian import dedup as _dedup

    migrated = _harvested_decls(conn, problem)
    if not migrated:
        return PipelineResult(outcome="success")  # nothing harvested

    # Point 4 — refine bridges into cite-mathlib DROPS: a wrapper whose body is a
    # pure mathlib citation (`X := Ideal.iInf_span_singleton hg`) is removed and
    # its consumers inlined to the mathlib lemma directly. 'cited' lifecycle drops
    # it from the harvest (so the probe + INDEX below exclude it); the probe's
    # olean rebuild + re-derivation is the integration gate.
    # NB: pass the DB-derived scope_index — at bridge time INDEX.md is empty (it's
    # written only on a bridge PASS, and the re-clean path clears it), so
    # `_load_decls`'s INDEX fallback would see no scope.
    scope_index = [(r["target_name"], r["target_file"]) for r in migrated
                   if r["target_name"] and r["target_file"]]
    cited = _dedup.cite_drop_aliases(
        workspace, problem, _dedup._load_decls(workspace, problem, scope_index)[0])
    if cited:
        for fqn, head in cited.items():
            conn.execute("UPDATE library_decls SET lifecycle = 'cited', "
                         "citation = ? WHERE problem = ? AND target_name = ?",
                         (head, problem, fqn))
        conn.commit()
        migrated = _harvested_decls(conn, problem)   # cited rows drop out

    # Gate B re-derives the root from the CLEANED Library, so its modules' oleans
    # must be current first. Cleanup edited the sources, leaving the migrate-time
    # oleans stale, and the gateway prober imports the on-disk olean as-is — it
    # does NOT rebuild a stale (or missing) dependency. Rebuild them so the probe
    # verifies the CURRENT cleaned Library, not a stale pre-cleanup snapshot. A
    # build failure here means the cleaned Library itself is broken (a cleanup
    # bug, e.g. a dangling cross-file reference) — a DISTINCT failure from a
    # genuinely non-mechanical statement, surfaced with the real lake error
    # rather than relabelled "load-bearing Defs".
    from .._lake import lake_build_modules
    modules = sorted({_library_module_of(r["target_file"])
                      for r in migrated if r["target_file"]})
    if modules:
        ok, detail = lake_build_modules(workspace, modules)
        if not ok:
            return PipelineResult(
                outcome="failed", failure_reason="librarian_cleaned_build_failed",
                failure_detail=("cleaned Library does not build — a cleanup bug, "
                                "NOT a non-mechanical statement: "
                                + (detail or "")[:600]))

    # anchor+claim new flow: the harvest targets are the marked DELIVERABLES,
    # which are fully migrated and build from the Library (checked just above,
    # together with their anchor closures — a dropped anchor would fail that
    # build). There is no root to re-derive: the root is never a deliverable and
    # may be vestigial scaffolding (`main : True`) that the keep-filter correctly
    # dropped. So the build check IS Gate B here — write the INDEX and finish,
    # skipping the root re-derivation probe (which would `librarian_no_root` on
    # the un-harvested root). cube_e2e 2026-07-02.
    has_deliverables = conn.execute(
        "SELECT 1 FROM goals WHERE problem = ? AND is_deliverable = 1 LIMIT 1",
        (problem,)).fetchone() is not None
    if has_deliverables:
        # Per-decl axiom re-verification at the topological END of the chain,
        # after cite_drop (the last rewrite). "builds" alone never inspects
        # the kernel's axiom graph — a `sorry`/`native_decide` introduced by a
        # post-migrate rewrite builds green. classic problems get this from
        # the root re-derivation probe below (its whitelist check walks the
        # root's transitive closure); deliverable problems have no root to
        # re-derive, so gate every harvested file's FINAL on-disk text
        # instead. The oleans are warm (rebuilt just above), so each file is
        # one warm elaboration. `whitelist=None` (unit tests) skips, matching
        # the migrate gate's contract; the dispatcher always passes one.
        if whitelist:
            from .gate import migrate_commit_gate
            for _tf in sorted({r["target_file"] for r in migrated
                               if r["target_file"]}):
                _fp = workspace / _tf
                try:
                    _txt = _fp.read_text(encoding="utf-8")
                except OSError as e:
                    return PipelineResult(
                        outcome="failed",
                        failure_reason="librarian_axiom_violation",
                        failure_detail=(f"deliverable axiom gate: cannot read "
                                        f"{_tf}: {e}"))
                gres = migrate_commit_gate(
                    _txt, _fp, whitelist=whitelist, workspace=workspace)
                if not gres.ok:
                    return PipelineResult(
                        outcome="failed",
                        failure_reason="librarian_axiom_violation",
                        failure_detail=(f"deliverable axiom gate: {_tf}: "
                                        f"{gres.detail}"))
        _write_library_index(
            conn, problem=problem, workspace=workspace,
            gate_b_line=("Gate B (deliverable build + per-decl axiom check): "
                         "PASSED — the marked deliverables + their anchor "
                         "closures build from the Library alone, and every "
                         "harvested decl's transitive axiom set is within "
                         "the authorized whitelist."))
        return PipelineResult(outcome="success")

    # Classic path only from here — the root statement is what Gate B
    # re-derives. Phase 6: this fetch (and its `librarian_no_root` failure)
    # must sit BELOW the deliverable branch: a pure-NL problem has no root
    # at all, and the old order failed it here before the deliverable
    # branch could take over (Analysis.metric_projection 2026-07-04; the
    # order was latent until pure-NL — every earlier deliverable problem
    # still had a trivial proved root that satisfied this query).
    root = conn.execute(
        "SELECT statement FROM goals WHERE problem = ? AND origin = 'root' "
        "AND status = 'proved' ORDER BY id LIMIT 1", (problem,)).fetchone()
    if not root or not (root["statement"] or "").strip():
        return PipelineResult(
            outcome="failed", failure_reason="librarian_no_root",
            failure_detail="no proved root statement for the bridge")
    statement = " ".join(root["statement"].split())

    probe = _bridge_probe_text(
        conn, problem=problem, statement=statement, migrated=migrated,
        workspace=workspace)
    if probe is None:
        return PipelineResult(
            outcome="failed", failure_reason="librarian_no_root",
            failure_detail="migrated root decl has no Library name; "
                           "cannot build the Gate B probe")

    res = _commit_bridge(
        probe, conn=conn, problem=problem, workspace=workspace,
        statement=statement, whitelist=whitelist or [])
    if res.outcome != "success":
        # The cleaned Library builds (checked above) but the original statement
        # cannot be re-derived from it by direct citation → a genuinely non-
        # mechanical bridge (load-bearing Defs mathlib can't express → operator /
        # RequestUserAmend). Surface the real gate error, not just a label.
        return PipelineResult(
            outcome="failed", failure_reason="librarian_bridge_not_mechanical",
            failure_detail=(
                "Gate B mechanical re-derivation failed — statement not re-derivable "
                "from the (buildable) cleaned Library by citation; likely a load-"
                "bearing Defs needing operator / RequestUserAmend: "
                + (res.failure_detail or "")[:600]))
    return res
