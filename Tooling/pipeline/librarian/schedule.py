"""librarian.schedule — split out of the former pipeline/librarian.py monolith."""
from __future__ import annotations

from ...state import db

from .classify import _merge_alias_map, _root_source


def file_dependency_graph(conn, *, problem: str, workspace,
                          lifecycles: "tuple[str, ...]" = ("classified", "migrated"),
                          ) -> "dict[str, set[str]]":
    """Map each placed Library file to the set of OTHER placed files it
    depends on. A file F depends on file G iff some decl in F uses (per the
    inventory dep graph) a decl placed in G.

    `lifecycles` selects which decls count as "placed" — the migrate phase
    uses the default `('classified','migrated')`; the cleanup phase passes
    `('migrated','cleaned','dropped')` so the import edges stay STABLE as
    decls advance migrated→cleaned/dropped within the phase (a dropped decl
    still physically lived in its file, so its consumers' F→G edge is real
    and must order F after G — §13 deferred-rewire). Cited decls are terminal
    and never placed."""
    from ...quality.librarian import inventory as _inv
    rows = db.library_decls_for(conn, problem)
    file_of = {r["slug"]: r["target_file"] for r in rows
               if r["target_file"] and r["lifecycle"] in lifecycles}
    # Cross-file edges follow the USAGE DAG (which lemma a proof term cites),
    # not the decomposition DAG (`InvDecl.deps`) — a file must migrate after
    # the files it actually references, else its imports don't resolve.
    usage = _inv.usage_graph(workspace, problem, file_of.keys(),
                             alias_map=_merge_alias_map(conn, problem),
                             root_source=_root_source(conn, problem, workspace))
    graph: "dict[str, set[str]]" = {f: set() for f in set(file_of.values())}
    for slug, f in file_of.items():
        for dep in usage.get(slug, set()):
            g = file_of.get(dep)
            if g and g != f:
                graph[f].add(g)
    return graph


def next_migrate_file(conn, *, problem: str, workspace) -> "str | None":
    """The next Library file ready to migrate: one with classified
    (not-yet-migrated) decls whose every dependency file is already
    migrated. Per-file migrate marks all of a file's decls 'migrated'
    together, so a file is either wholly classified or wholly migrated —
    'fully migrated' is just lifecycle=='migrated'. Ties broken by path so
    the chain is reproducible. Returns None when no classified decls
    remain. Falls back to the first classified file when none is ready —
    an acyclic DAG always has a ready file, so this only fires on a
    classify bug, and the build gate then surfaces the unresolved import
    honestly rather than the chain silently stalling."""
    rows = db.library_decls_for(conn, problem)
    classified = sorted({r["target_file"] for r in rows
                         if r["lifecycle"] == "classified"
                         and r["target_file"]})
    if not classified:
        return None
    migrated = {r["target_file"] for r in rows
                if r["lifecycle"] == "migrated" and r["target_file"]}
    graph = file_dependency_graph(conn, problem=problem, workspace=workspace)
    for f in classified:
        if all(dep in migrated for dep in graph.get(f, set())):
            return f
    return classified[0]


def file_work_kind(conn, *, problem: str, target_file: str) -> "str | None":
    """The current step for ONE Library file (#92 per-file unit dispatch).
    'migrate' if the file still has `classified` decls; else 'cleanup' if it
    still has `migrated` (un-cleaned) decls (§13 3c-2 per-file dedup); else
    None — a file whose decls are all `cleaned`/`dropped` is done (the
    whole-problem bridge Gate B follows once every file is cleaned)."""
    ls = {r["lifecycle"] for r in db.library_decls_for(conn, problem)
          if r["target_file"] == target_file}
    if "classified" in ls:
        return "migrate"
    if "migrated" in ls:
        return "cleanup"
    return None


def ready_file_work(conn, *, problem: str, workspace,
                    in_flight: "set[str] | tuple" = ()) -> "list[tuple[str, str]]":
    """The set of Library FILES dispatchable RIGHT NOW as independent migrate
    units (#92 dynamic file pipeline), each as `('migrate', target_file)`:

      - f's decls are still `classified` AND every file f depends on is already
        `migrated` (importable). A file migrates against its deps' migrated
        (original-signature) form — consistent with the original proofs.

    v0.3 (plan §3): cleanup is removed, so migrate is the only per-file work;
    a wholly `migrated` file is done (the whole-problem bridge follows once all
    files are migrated). `done = migrated` is the readiness currency. Files in
    `in_flight` are excluded; order-stable by path so independent files run
    concurrently in the pool.
    """
    from collections import defaultdict
    in_flight = set(in_flight)
    rows = db.library_decls_for(conn, problem)
    by_file: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["target_file"] and r["lifecycle"] in ("classified", "migrated"):
            by_file[r["target_file"]].append(r)

    def _phase(rs) -> str:
        # Least-advanced lifecycle present — defensive against a half-moved
        # file (treat as the earlier stage; never double-dispatch).
        ls = {r["lifecycle"] for r in rs}
        return "classified" if "classified" in ls else "migrated"

    phase = {f: _phase(rs) for f, rs in by_file.items()}
    migrated = {f for f, ph in phase.items() if ph == "migrated"}
    graph = file_dependency_graph(conn, problem=problem, workspace=workspace)
    work: list[tuple[str, str]] = []
    for f in sorted(phase):
        if f in in_flight:
            continue
        if phase[f] == "classified" and all(
                dep in migrated for dep in graph.get(f, set())):
            work.append(("migrate", f))
    return work


def ready_cleanup_files(conn, *, problem: str, workspace,
                        in_flight: "set[str] | tuple" = ()) -> "list[tuple[str, str]]":
    """The set of Library FILES dispatchable RIGHT NOW as independent cleanup
    units (§13 3c-2 per-file dedup), each as `('cleanup', target_file)`:

      - f still has `migrated` (un-cleaned) decls AND every file f depends on is
        already DONE (all its decls `cleaned`/`dropped`). Bottom-up: a file is
        cleaned only after the files it imports, so when a consumer runs, every
        drop from its dependencies is already recorded in the DB rename-map and
        it can self-apply them (deferred-rewire, lock-free — §13). A fully-
        `dropped` file (no survivors) counts as done.

    Mirrors `ready_file_work` (the migrate analogue): `done = cleaned/dropped`
    is the readiness currency, files in `in_flight` are excluded, order-stable
    by path so independent files run concurrently in the pool. The dependency
    graph spans `migrated`/`cleaned`/`dropped` so its import edges stay stable
    as decls advance within the phase."""
    from collections import defaultdict
    in_flight = set(in_flight)
    rows = db.library_decls_for(conn, problem)
    by_file: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["target_file"] and r["lifecycle"] in (
                "migrated", "cleaned", "dropped"):
            by_file[r["target_file"]].append(r)

    def _phase(rs) -> str:
        # 'migrated' (work left) if any decl is still un-cleaned, else 'done'.
        return "migrated" if any(r["lifecycle"] == "migrated" for r in rs) \
            else "done"

    phase = {f: _phase(rs) for f, rs in by_file.items()}
    done = {f for f, ph in phase.items() if ph == "done"}
    graph = file_dependency_graph(
        conn, problem=problem, workspace=workspace,
        lifecycles=("migrated", "cleaned", "dropped"))
    work: list[tuple[str, str]] = []
    for f in sorted(phase):
        if f in in_flight:
            continue
        if phase[f] == "migrated" and all(
                dep in done for dep in graph.get(f, set())):
            work.append(("cleanup", f))
    return work


def _harvested_decls(conn, problem: str) -> list:
    """Decls actually placed in the Library — 'migrated' (pre-cleanup) plus
    'cleaned' (Step 4 done). The set bridge re-derives against and INDEX
    records, robust to whether cleanup has run."""
    return [r for r in db.library_decls_for(conn, problem)
            if r["lifecycle"] in ("migrated", "cleaned")]


def _affected_cone(graph: dict, touched: set) -> set:
    """`touched` ∪ every file transitively importing one — a signature change
    in F invalidates every G that (transitively) imports F."""
    rev: dict = {}
    for f, deps in graph.items():
        for d in deps:
            rev.setdefault(d, set()).add(f)
    cone, frontier = set(touched), list(touched)
    while frontier:
        x = frontier.pop()
        for imp in rev.get(x, ()):
            if imp not in cone:
                cone.add(imp)
                frontier.append(imp)
    return cone


def _topo_files(graph: dict, files: set) -> list:
    """Topologically order `files` deps-first (a file after every dep that is
    also in the set) so a write_olean rebuild publishes fresh dependency
    oleans before their importers build. Stable; cycle → leftovers appended."""
    files = set(files)
    indeg = {f: len([d for d in graph.get(f, ()) if d in files]) for f in files}
    users: dict = {f: [] for f in files}
    for f in files:
        for d in graph.get(f, ()):
            if d in files:
                users[d].append(f)
    ready = sorted(f for f in files if indeg[f] == 0)
    out: list = []
    while ready:
        f = ready.pop(0)
        out.append(f)
        for u in users[f]:
            indeg[u] -= 1
            if indeg[u] == 0:
                ready = sorted(ready + [u])
    out += [f for f in files if f not in out]   # cycle fallback
    return out
