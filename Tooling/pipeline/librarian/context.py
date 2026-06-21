"""librarian.context — split out of the former pipeline/librarian.py monolith."""
from __future__ import annotations

from pathlib import Path as _Path
from ...state import db

from . import classify, schedule
from ._base import CLASSIFY_FILE_LINE_BUDGET
from .astslice import _library_module_of
from .classify import _decl_line_counts, _root_source, _toposort_intra_file
from .schedule import _harvested_decls


# ---------------------------------------------------------------------
# Stage C — Context.md compiler (per work kind)
# ---------------------------------------------------------------------
# Librarian context is problem/decl-centric (vs Strategist's goal-tree
# Context.md). Each work kind sees only what it needs:
#   classify — the kept (deduped) decls + their deps (the layout surface)
#   migrate  — the one target decl's original source + its dedup verdict


def _read_statement(conn, problem: str, slug: str) -> str:
    row = conn.execute(
        "SELECT statement FROM goals WHERE problem = ? AND slug = ?",
        (problem, slug),
    ).fetchone()
    return (row["statement"] if row else "") or ""


def _strategy_proofs_of(workspace, lean_path_rel: str) -> "list[str]":
    """Workspace-relative paths of the `_strategy_s<N>.lean` files that a goal's
    `L_<slug>.lean` (at `lean_path_rel`) imports — the files holding the ACTUAL
    tactic proof (the `def := @…sN` alias / thin `theorem … := by exact sN`
    wrapper just points there). Lets a hole's context point past the one-line
    alias to the real proof to port. Best-effort: empty if missing / no strategy
    import."""
    import re as _re
    from pathlib import Path as _Path
    p = workspace / lean_path_rel
    if not p.exists():
        return []
    proofs_rel = _Path(lean_path_rel).parent
    rx = _re.compile(r"import\s+Problems\.[\w.]+\.proofs\.(_strategy_s\d+)\b")
    out: list[str] = []
    for m in rx.finditer(p.read_text(encoding="utf-8", errors="replace")):
        sp = (proofs_rel / f"{m.group(1)}.lean").as_posix()
        if (workspace / sp).exists() and sp not in out:
            out.append(sp)
    return out


def compile_librarian_context(
    conn, *, problem: str, work_kind: str, attempts_dir,
    workspace, target_file: str | None = None,
    holes: "list[str] | None" = None,
    solo_hole: "str | None" = None,
    prev_error: "str | None" = None,
    prior_plan: "str | None" = None,
) -> "_Path":
    """Write attempts_dir/Context.md for a Librarian work spawn.

    `work_kind` ∈ {classify, migrate}. `target_file` is required
    for migrate (the Library file to write — its classified decls in
    file_order, plus the sibling modules it may import).

    `holes` (migrate only, seed mode): when non-None, `patch.lean` is
    pre-seeded with a mechanically-relabelled draft and the agent's job is
    to finish it, not write it. A non-empty list names the decls left as
    `sorry` holes to fill; an empty list means the draft is complete but
    build-failed (fix it). When None, the agent writes the file from
    scratch (cold).

    `prev_error` (classify): the verify rejection from the PRIOR attempt —
    classify is a one-shot per dispatch and the chain re-dispatches a fresh
    spawn on rejection, so without this the agent never learns it (e.g.)
    omitted a kept decl and re-drops a different one until the chain STALLs.
    Surfaced verbatim at the top of the plan task."""
    from ...quality.librarian import inventory as _inv

    lines: list[str] = [f"# Librarian — {work_kind} — {problem}", ""]

    if work_kind == "classify":
        if prev_error and prior_plan:
            # The retry instruction depends on WHAT was rejected. A size/cycle
            # rejection needs a real re-partition (moving many decls across the
            # named files); a "smallest change, keep every placement" ask
            # actively obstructs that. A decl-drop / other rejection is the
            # opposite: re-deriving the whole 200+-decl layout from scratch
            # re-drops a *different* decl each time (whack-a-mole), so there the
            # incremental "edit the prior plan" ask is right.
            _is_regroup = ("usage cycle" in prev_error
                           or ("source lines" in prev_error
                               and "budget" in prev_error))
            if _is_regroup:
                lines += [
                    "## Your previous plan was REJECTED (file too big / cyclic) "
                    "— RE-PARTITION the named files", "",
                    "The rejection:", "", "```", prev_error[-1500:], "```", "",
                    "This needs a REAL re-partition, NOT a one-line edit. Using "
                    "the `cites` graph below (declarations are listed in "
                    "dependency order), move declarations among the NAMED files "
                    "so the import graph is a DAG — a file only cites "
                    "declarations in files it imports, and no two files cite "
                    "into each other — and keep each file under budget. Expect "
                    "to change many placements AMONG THE NAMED FILES; KEEP every "
                    "placement outside them exactly as it is. Output the "
                    "COMPLETE edited plan.", "",
                    "### Your previous plan (re-partition this)", "",
                    "```json", prior_plan.strip(), "```", ""]
            else:
                lines += [
                    "## Your previous plan was REJECTED — EDIT it, do not "
                    "re-plan", "", "The rejection:", "", "```",
                    prev_error[-1200:], "```", "",
                    "Your previous plan is below. START FROM IT and make the "
                    "SMALLEST change that clears the rejection — add the missing "
                    "declaration(s) to the right file — and KEEP every other "
                    "placement exactly as it is. (Re-deriving the whole layout "
                    "from scratch is what dropped declarations last time.) "
                    "Output the COMPLETE edited plan.", "",
                    "### Your previous plan (edit this)", "",
                    "```json", prior_plan.strip(), "```", ""]
        elif prev_error:
            lines += [
                "## Your previous layout was REJECTED — fix exactly this and "
                "re-emit the full plan", "", "```", prev_error[-1200:], "```",
                "", "Every kept declaration below MUST appear in exactly one "
                "file's `decls` — re-check the full list against your plan "
                "before emitting.", ""]
        kept = db.library_decls_for(conn, problem, lifecycle="deduped")
        lines.append(f"_{len(kept)} kept declarations to lay out._")
        lines.append("")
        # Existing Library tree — naming consistency: a layout that invents
        # `ManifoldBdry/` next to an existing `ManifoldBoundary/` (same
        # concept, two area dirs — stokes 2026-06-11) builds fine but is a
        # PR blocker. The agent should reuse existing directories whenever
        # the topic matches, and only mint a new one for genuinely new areas.
        lib_root = workspace / "Library"
        existing = sorted(
            str(p.relative_to(lib_root)).replace("\\", "/")
            for p in lib_root.rglob("*") if p.is_dir()
            and not p.name.startswith((".", "_"))) if lib_root.exists() else []
        if existing:
            lines.append("## Existing Library directories (reuse on topic "
                         "match; do not mint near-duplicates)")
            lines.append("")
            lines += [f"- `Library/{d}/`" for d in existing]
            lines.append("")
        # Files other problems already own — migrate writes whole files, so
        # these paths are TAKEN: the plan must pick different file names
        # (the mechanical verify rejects collisions).
        owned = sorted({r["target_file"].replace("\\", "/")
                        for r in conn.execute(
                            "SELECT DISTINCT target_file FROM library_decls "
                            "WHERE problem != ? AND lifecycle IN "
                            "('classified', 'migrated', 'cleaned') "
                            "AND target_file IS NOT NULL", (problem,))})
        if owned:
            lines.append("## Existing Library FILES (taken — your plan must "
                         "use different file names)")
            lines.append("")
            lines += [f"- `{f}`" for f in owned]
            lines.append("")
        # Show the agent the proof-term CITATION graph (`_decl_usage`) — the
        # SAME graph verify_merged_file_sizes / commit_classify order the layout
        # on — NOT build_inventory's decomposition deps. Listed in dependency
        # (topological) order so the agent can lay files out as contiguous
        # groups and keep the import graph acyclic; feeding the decomposition
        # DAG instead is what let the agent build file-level citation cycles it
        # never saw (residue_thm 11-file SCC -> 5833 lines, 2026-06-18).
        kept_slugs = [r["slug"] for r in kept]
        usage = classify._decl_usage(conn, problem, kept_slugs, workspace)
        defs_set = set(_inv.defs_decls(workspace, problem)) & set(kept_slugs)
        ordered = _toposort_intra_file(kept_slugs, usage, defs_set)
        # Source size per decl — the agent budgets file sizes with these
        # (verify_classify enforces CLASSIFY_FILE_LINE_BUDGET per planned file).
        sizes = _decl_line_counts(workspace, problem, kept_slugs)
        lines += [
            "## File layout rule (your plan is graded on this)", "",
            "Lay out files so the import graph is a **DAG**: a file may only "
            "cite declarations in files it imports, and **no two files may cite "
            "into each other** — a cyclic file group is an un-splittable "
            "circular import, gets merged into one Lean module, and then blows "
            f"the ~{CLASSIFY_FILE_LINE_BUDGET}-line size budget. The "
            "declarations below are in dependency (topological) order — each "
            "`cites` only earlier ones — so laying them into files as roughly "
            "CONTIGUOUS groups keeps the imports acyclic. Group mutually-related "
            "declarations together; keep each file under budget.", ""]
        lines.append("## Kept declarations — dependency order "
                     "(slug + size + cites + statement)")
        lines.append("")
        for slug in ordered:
            cites = ", ".join(
                f"`{s}`" for s in sorted(usage.get(slug, set()))) or "—"
            stmt = " ".join(_read_statement(conn, problem, slug).split())
            lines.append(f"### {slug}")
            lines.append(f"- ~{sizes.get(slug, 0)} source lines")
            lines.append(f"- cites: {cites}")
            lines.append(f"- `{stmt}`" if stmt else "- _(no statement)_")
            lines.append("")

    elif work_kind == "migrate":
        if not target_file:
            raise ValueError("migrate work requires target_file")
        rows = [r for r in db.library_decls_for(conn, problem)
                if r["target_file"] == target_file
                and r["lifecycle"] == "classified"]
        rows.sort(key=lambda r: (r["file_order"]
                                 if r["file_order"] is not None else 0))
        target_module = _library_module_of(target_file)
        lines.append(f"## Migrate file `{target_file}`")
        lines.append("")
        lines.append(f"- module: `{target_module}`")
        # Derived sibling imports (GAP 2): the Library modules this file's
        # decls depend on — already migrated (topological order).
        graph = schedule.file_dependency_graph(conn, problem=problem,
                                      workspace=workspace)
        dep_files = sorted(graph.get(target_file, set()))
        if dep_files:
            lines.append("- sibling Library modules you may import:")
            for df in dep_files:
                lines.append(f"    - `{_library_module_of(df)}`")
        else:
            lines.append("- sibling Library modules you may import: "
                         "none (Mathlib only)")
        lines.append("")
        lines.append(f"_{len(rows)} declaration(s) to migrate, in this "
                     "exact order:_")
        lines.append("")
        defs_names = set(_inv.defs_decls(workspace, problem))
        # A Defs declaration's body is Gate-D-locked — show the verbatim
        # Defs.lean once so the agent reproduces it character for character.
        if any(r["slug"] in defs_names for r in rows):
            defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
            if defs_path.exists():
                lines.append("## Defs.lean (definitions are locked — "
                             "reproduce verbatim)")
                lines.append("")
                lines.append("```lean")
                lines.append(defs_path.read_text(
                    encoding="utf-8", errors="replace").rstrip())
                lines.append("```")
                lines.append("")
        hole_set = set(holes or [])
        if solo_hole is not None:
            # Incremental per-decl mode (#87): patch.lean is a ONE-declaration
            # seed that imports the decls migrated into this file so far + the
            # sibling modules. The agent finishes just that one declaration.
            lines.append("## Finish one declaration")
            lines.append("")
            lines.append(
                f"`patch.lean` imports the declarations already migrated into "
                f"this file plus the sibling modules, then holds the single "
                f"declaration `{solo_hole}` (marked ⛏ FILL THIS below) with a "
                f"`sorry` body. **Finish exactly that one declaration** — refer "
                f"to the imported siblings by name, don't restate them. Keep "
                f"its signature verbatim unless it is flagged a signature hole "
                f"below (then restate it Defs-free).")
            lines.append("")
        elif holes is not None:
            # Whole-file seed (no live caller after the #87 incremental
            # rework; kept for the agentless / manual fallback): finish a
            # mechanically-relabelled draft in place, don't rewrite it.
            lines.append("## You are given a seed — finish it, don't rewrite")
            lines.append("")
            lines.append(
                "`patch.lean` is pre-filled with a mechanically-relabelled "
                "draft of this whole file: namespaces, imports and every "
                "non-hole declaration are already correct. **Do not rewrite "
                "the working declarations or change their signatures.**")
            lines.append("")
            if hole_set:
                lines.append(
                    f"Fill the **{len(hole_set)} `sorry` hole(s)** below "
                    "(marked ⛏), keeping each signature exactly as seeded:")
                for h in holes:
                    lines.append(f"  - `{h}`")
            else:
                lines.append(
                    "The draft is complete but does not build — fix the "
                    "build error(s) without weakening any signature.")
            lines.append("")
        lines.append("## Declarations")
        lines.append("")
        # Precompute proof-term references (raw, per slug), dedup verdicts, and
        # goal proof paths once: a hole gets handed (a) its real proof source
        # (alias resolved to the `_strategy_s<N>.lean` holding the tactic body)
        # and (b) the proofs of any sibling dedup'd INTO it, which it must
        # inline — not just a name to rediscover. Reused by the redirect table.
        ref = _inv.referenced_slugs(
            workspace, problem, [r["slug"] for r in rows],
            root_source=_root_source(conn, problem, workspace))
        by_slug = {r["slug"]: r for r in db.library_decls_for(conn, problem)}
        lean_paths = {
            row["slug"]: row["lean_path"]
            for row in conn.execute(
                "SELECT slug, lean_path FROM goals WHERE problem = ?",
                (problem,)).fetchall()}
        for i, r in enumerate(rows, 1):
            slug = r["slug"]
            is_hole = (slug == solo_hole
                       or (solo_hole is None and slug in hole_set))
            if slug == solo_hole:
                tag = " ⛏ FILL THIS"
            elif solo_hole is None and slug in hole_set:
                tag = " ⛏ HOLE — fill this"
            else:
                tag = ""
            lines.append(f"### {i}. `{slug}`{tag}")
            if r["verdict"] and r["verdict"] != "keep":
                lines.append(f"- dedup verdict: {r['verdict']} → cite "
                             f"`{r['citation']}`")
            if slug in defs_names:
                lines.append("- a Defs declaration — see the locked "
                             "Defs.lean above; reproduce its signature "
                             "and body.")
                lines.append("")
                continue
            stmt = " ".join(_read_statement(conn, problem, slug).split())
            lines.append("- statement (signature — copy verbatim):")
            lines.append(f"  `{stmt}`" if stmt else "  _(no statement)_")
            lp = lean_paths.get(slug)
            if lp:
                lines.append("- proof source (read for the body to port): "
                             f"`{lp}`")
                # The L_<slug>.lean is a thin alias/wrapper; the real tactic
                # proof lives in the `_strategy_s<N>.lean` it imports.
                for sp in _strategy_proofs_of(workspace, lp):
                    lines.append(f"    - actual proof body: `{sp}`")
            # Holes only: surface the proofs of siblings dedup'd INTO this decl
            # (merge / drop, no Library home). The hole exists to ABSORB them,
            # so the agent must INLINE their proofs — hand over the sources
            # instead of making it discover the drop and hunt the files.
            if is_hole:
                absorbed = []
                for dep in sorted(ref.get(slug, set())):
                    drow = by_slug.get(dep)
                    if (drow and drow["verdict"] in ("merge", "drop")
                            and not drow["target_file"]):
                        absorbed.append((dep, drow["verdict"]))
                if absorbed:
                    lines.append(
                        "- absorbed siblings (dedup'd into this decl — they have "
                        "no Library home, so inline their proofs):")
                    for dep, verdict in absorbed:
                        dlp = lean_paths.get(dep)
                        loc = f" — proof: `{dlp}`" if dlp else ""
                        for sp in (_strategy_proofs_of(workspace, dlp)
                                   if dlp else []):
                            loc += f", body: `{sp}`"
                        lines.append(f"    - `{dep}` ({verdict}){loc}")
            lines.append("")
        # Redirect table (G3): non-keep siblings these decls cite + what to
        # replace each with (reuses `ref` / `by_slug` precomputed above). A
        # `sorry`-hole body that referenced a merged / dropped / cited sibling
        # must use the canonical / mathlib / Library name instead.
        all_refs: set[str] = set().union(*ref.values()) if ref else set()
        redirects = [
            (s, by_slug[s]["verdict"], by_slug[s]["citation"])
            for s in sorted(all_refs)
            if s in by_slug and by_slug[s]["citation"]
            and by_slug[s]["verdict"] in (
                "merge", "drop", "cite-mathlib", "cite-library")]
        if redirects:
            lines.append("## Sibling redirects (a referenced sibling was not "
                         "kept — use the replacement)")
            lines.append("")
            for s, verdict, cit in redirects:
                lines.append(f"- `{s}` → `{cit}`  ({verdict})")
            lines.append("")

    elif work_kind == "bridge":
        # Gate B: re-derive the original root `theorem main` from the Library.
        root = conn.execute(
            "SELECT slug, statement FROM goals WHERE problem = ? AND "
            "origin = 'root' AND status = 'proved' ORDER BY id LIMIT 1",
            (problem,)).fetchone()
        stmt = " ".join((root["statement"] if root else "").split())
        lines.append("## Re-derive the original root from the Library")
        lines.append("")
        lines.append("- original statement (prove this **verbatim** as "
                     "`theorem main : <statement>`):")
        lines.append(f"  `{stmt}`" if stmt else "  _(no root statement)_")
        lines.append("")
        # Keystone candidates: the placed forms of the decls the root's
        # winning strategy used directly — the most likely one-liner.
        migrated = {r["slug"]: r for r in _harvested_decls(conn, problem)}
        inv = _inv.build_inventory(conn, workspace, problem)
        root_deps = next((d.deps for d in inv.decls
                          if d.origin == "root"), [])
        keystones = [migrated[s] for s in root_deps if s in migrated]
        if keystones:
            lines.append("- likely keystone(s) (migrated form of what the "
                         "original proof used):")
            for r in keystones:
                lines.append(f"    - `{r['target_name'] or r['slug']}` "
                             f"(`{r['target_file']}`)")
            lines.append("")
        lines.append(f"## Library declarations from this problem "
                     f"({len(migrated)})")
        lines.append("")
        for r in migrated.values():
            lines.append(f"- `{r['target_name'] or r['slug']}` "
                         f"→ `{r['target_file']}`")

    else:
        raise ValueError(f"unknown work_kind: {work_kind!r}")

    ctx = attempts_dir / "Context.md"
    ctx.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ctx
