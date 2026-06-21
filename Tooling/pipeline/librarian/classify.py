"""librarian.classify — split out of the former pipeline/librarian.py monolith."""
from __future__ import annotations

import re
from ...state import db

from ._base import CLASSIFY_FILE_LINE_BUDGET, ClassifyFile, ClassifyPlan, _code_normalized, _load_json
from .astslice import _COMPLEX_DECL_RE, _DECL_COMMENT_RE, _defs_decl_source


def parse_classify(json_text: str) -> tuple[ClassifyPlan | None, str]:
    """Parse the classify agent's layout plan: `{"files": [...]}`."""
    obj, err = _load_json(json_text)
    if err:
        return None, err
    if not isinstance(obj, dict):
        return None, f"expected object with 'files', got {type(obj).__name__}"
    files_raw = obj.get("files")
    if not isinstance(files_raw, list) or not files_raw:
        return None, "missing/empty 'files' array"

    files: list[ClassifyFile] = []
    for i, f in enumerate(files_raw):
        if not isinstance(f, dict):
            return None, f"file {i}: not an object"
        path = f.get("path")
        if not path or not isinstance(path, str):
            return None, f"file {i}: missing/invalid 'path'"
        decls = f.get("decls")
        if not isinstance(decls, list) or not decls:
            return None, f"file {i} ({path}): missing/empty 'decls'"
        if not all(isinstance(d, str) for d in decls):
            return None, f"file {i} ({path}): non-string in 'decls'"
        imports = f.get("imports") or []
        if not isinstance(imports, list) or \
                not all(isinstance(m, str) for m in imports):
            return None, f"file {i} ({path}): 'imports' must be string list"
        files.append(ClassifyFile(path=path, imports=list(imports),
                                  decls=list(decls)))
    return ClassifyPlan(files=files), ""


def _decl_line_counts(workspace, problem: str,
                      slugs: "set[str] | list[str]") -> "dict[str, int]":
    """{slug: line count of its proof file} — the classify size estimate.
    A missing proof file counts 0 (other gates own that failure)."""
    from ...quality.librarian import inventory as _inv
    proofs = db.problem_dir(workspace, problem) / "proofs"
    out: dict[str, int] = {}
    for slug in slugs:
        p = _inv.resolve_ci(proofs, f"L_{slug}.lean")
        try:
            out[slug] = len(p.read_text(encoding="utf-8").splitlines()) if p else 0
        except OSError:
            out[slug] = 0
    return out


def verify_classify(plan: ClassifyPlan, kept_slugs: set[str],
                    decl_lines: "dict[str, int] | None" = None,
                    owned_files: "set[str] | None" = None) -> str:
    """Reject a layout plan that doesn't cover exactly the kept decls,
    imports a non-Library module, has an import cycle, (when `decl_lines` is
    given) plans a file over the size budget, or (when `owned_files` is given)
    places decls into a file another problem already owns — migrate writes
    whole files, so a shared path can only clobber (the topic-natural name is
    often already taken: form_coord self/cont both replanned into comp's
    FormCoordChange.lean, 2026-06-11). "" on ok."""
    # Every kept decl placed exactly once; no stray slugs.
    placed: list[str] = [d for f in plan.files for d in f.decls]
    placed_set = set(placed)
    if len(placed) != len(placed_set):
        dup = next(d for d in placed if placed.count(d) > 1)
        return f"decl {dup!r} placed in more than one file"
    missing = kept_slugs - placed_set
    if missing:
        return f"kept decls not placed: {sorted(missing)}"
    stray = placed_set - kept_slugs
    if stray:
        return f"plan places non-kept decls: {sorted(stray)}"

    # Imports must be Library modules; build the file-module graph.
    modules = {_path_to_module(f.path): f for f in plan.files}
    for f in plan.files:
        for imp in f.imports:
            if not imp.startswith("Library."):
                return f"{f.path}: import {imp!r} is not a Library module"
    # Acyclicity over the intra-plan dependency edges.
    cycle = _find_cycle({
        _path_to_module(f.path): [m for m in f.imports if m in modules]
        for f in plan.files
    })
    if cycle:
        return f"import cycle: {' -> '.join(cycle)}"

    # File ownership: a path another problem already migrated into is taken.
    if owned_files:
        for f in plan.files:
            if f.path.replace("\\", "/") in owned_files:
                return (f"{f.path}: already holds another problem's migrated "
                        f"declarations — pick a DIFFERENT file name in the "
                        f"same directory (e.g. suffix by sub-topic); shared "
                        f"definitions are cited automatically, your file only "
                        f"needs your own declarations")

    # Size budget (mathlib longFile, see CLASSIFY_FILE_LINE_BUDGET above).
    if decl_lines is not None:
        for f in plan.files:
            est = sum(decl_lines.get(d, 0) for d in f.decls)
            if est > CLASSIFY_FILE_LINE_BUDGET:
                return (f"{f.path}: ~{est} source lines "
                        f"(budget {CLASSIFY_FILE_LINE_BUDGET}; mathlib's "
                        f"longFile linter caps files at 1500) — split it "
                        f"into sub-topic files")
    return ""


def _path_to_module(path: str) -> str:
    """`Library/LinearAlgebra/Jordan.lean` -> `Library.LinearAlgebra.Jordan`."""
    p = path[:-5] if path.endswith(".lean") else path
    return p.replace("/", ".").replace("\\", ".")


def _find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """DFS cycle detection; returns a cycle path or None."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    stack: list[str] = []

    def dfs(n: str) -> list[str] | None:
        color[n] = GRAY
        stack.append(n)
        for m in graph.get(n, []):
            if color.get(m, BLACK) == GRAY:
                return stack[stack.index(m):] + [m]
            if color.get(m, BLACK) == WHITE:
                r = dfs(m)
                if r:
                    return r
        stack.pop()
        color[n] = BLACK
        return None

    for n in graph:
        if color[n] == WHITE:
            r = dfs(n)
            if r:
                return r
    return None


# ---------------------------------------------------------------------
# Commit (side effects into library_decls)
# ---------------------------------------------------------------------

def _toposort_intra_file(decls: list[str],
                         usage: "dict[str, set[str]]",
                         defs_set: "set[str] | None" = None) -> list[str]:
    """Order one file's decls so each is emitted AFTER every same-file
    sibling it cites (Lean resolves names top-to-bottom). Stable Kahn: where
    usage doesn't force an order, Defs decls (defs/instances — `defs_set`)
    are emitted before proof decls, then the agent's original sequence is
    preserved (tie-break by `(not-a-Def, original position)`).

    The Defs-first tie-break is load-bearing for INSTANCES: a proof that
    uses an instance (e.g. `OrientedManifold (Bdry n M)` via `instBdryOriented`)
    resolves it implicitly by typeclass search — it never NAMES the instance,
    so `usage_graph` records no proof→instance edge. Without the bias, the
    instance can land after its users (stokes PerBumpStokes: instBdryOriented
    at file_order 62 while users sat at 51-61 → `failed to synthesize
    OrientedManifold (?n) (Bdry n M)` at migrate, 2026-06-16). Biasing the
    ready-queue so a dependency-free Def is emitted first hoists it above its
    implicit users; a real edge (a Def that genuinely cites a proof) still
    overrides via indeg, so it stays sound.

    A cycle (shouldn't arise from a valid proof forest) leaves the offending
    decls in original order — the build gate then surfaces the unresolved
    reference honestly."""
    ds = defs_set or set()
    in_file = set(decls)
    pos = {s: i for i, s in enumerate(decls)}
    # Ready-queue order: Defs decls first (0), then proofs (1); ties by
    # original position. Hoists implicitly-used instances above their users.
    key = lambda s: (0 if s in ds else 1, pos[s])  # noqa: E731
    dep = {s: {u for u in usage.get(s, set()) if u in in_file and u != s}
           for s in decls}
    users: dict[str, list[str]] = {s: [] for s in decls}
    for s in decls:
        for u in dep[s]:
            users[u].append(s)
    indeg = {s: len(dep[s]) for s in decls}
    ready = sorted((s for s in decls if indeg[s] == 0), key=key)
    result: list[str] = []
    placed: set[str] = set()
    while ready:
        s = ready.pop(0)
        result.append(s)
        placed.add(s)
        newly = []
        for w in users[s]:
            indeg[w] -= 1
            if indeg[w] == 0:
                newly.append(w)
        if newly:
            ready = sorted(ready + newly, key=key)
    if len(result) != len(decls):           # cycle fallback
        result += [s for s in decls if s not in placed]
    return result


def _reorder_decls_by_intrafile_refs(text: str) -> str:
    """Reorder a cleaned Library file's theorem/lemma/def blocks so each is
    emitted AFTER every same-file sibling it references.

    Closes the gap where cleanup (dedup/simplify) rewrites a proof to cite a
    different sibling — introducing a new intra-file dependency — but
    `file_order` was frozen at classify time from the IMPORT-based usage graph
    of the PRE-cleanup proofs and never recomputed (eckart_young: dedup rewired
    `termwise_eigenvalue_bound` to cite `eigen_pointwise_lower_bound` + dropped
    its two helpers, leaving a forward reference that fails the whole-Library
    build). Reads the FINAL file's actual references — those refs are same-file
    FQN/bare names, not imports, so `usage_graph` (import-based) can't see them.

    Conservative + build-gated:
      - SKIP files with structure/class/instance/inductive/abbrev/axiom heads
        (`_DECL_NAME_RE` doesn't slice them → mis-slice risk) — return as-is.
      - SKIP on duplicate decl names (ambiguous slicing).
      - No-op when the order is already sound.
      - The subsequent zero-warning build gate is the correctness backstop: a
        reorder that (mis-parse) broke the build fails the gate, never ships."""
    from ...quality.librarian.cleanup._common import _DECL_NAME_RE, _block_start
    if _COMPLEX_DECL_RE.search(text):
        return text
    heads = list(_DECL_NAME_RE.finditer(text))
    if len(heads) < 2:
        return text
    names = [h.group(1) for h in heads]
    if len(set(names)) != len(names):
        return text
    spans: "dict[str, tuple[int, int]]" = {}
    for i, h in enumerate(heads):
        start = _block_start(text, h.start())
        if i + 1 < len(heads):
            end = _block_start(text, heads[i + 1].start())
        else:
            m = re.search(r"(?m)^end\b", text[h.start():])
            end = (h.start() + m.start()) if m else len(text)
        spans[names[i]] = (start, end)
    # Edge X→Y: Y's name appears (whole token, comments stripped) in X's block.
    # `\b<name>\b` matches both a bare ref and the tail of an FQN ref (the `.`
    # before is a word boundary); mirrors commit_classify's Defs-edge scan.
    nameset = set(names)
    code = {n: _DECL_COMMENT_RE.sub(" ", text[s:e]) for n, (s, e) in spans.items()}
    usage = {n: {y for y in nameset if y != n
                 and re.search(rf"\b{re.escape(y)}\b", code[n])}
             for n in names}
    order = _toposort_intra_file(names, usage, set())
    if order == names:
        return text
    body = "".join(text[spans[n][0]:spans[n][1]] for n in order)
    return text[:spans[names[0]][0]] + body + text[spans[names[-1]][1]:]


def _merge_file_sccs(fgraph: dict, decls_in: dict) -> dict:
    """Collapse each strongly-connected component of the file-usage graph to
    one canonical file. A set of files that (transitively) import each other
    is physically un-splittable across Lean modules — leaving them apart is a
    circular import that can't be topologically ordered or built. The SCC's
    decls all belong in ONE file. Returns {file_path: canonical_path}; a file
    not in a multi-file SCC maps to itself. Canonical = the member with the
    most decls (lexicographic tie-break), for a deterministic choice."""
    nodes = list(fgraph)
    reach: dict = {n: set() for n in nodes}
    for n in nodes:
        stack = list(fgraph.get(n, ()))
        while stack:
            m = stack.pop()
            if m not in reach[n]:
                reach[n].add(m)
                stack.extend(fgraph.get(m, ()))
    canon: dict = {}
    seen: set = set()
    for n in nodes:
        if n in seen:
            continue
        comp = {n} | {m for m in nodes if m in reach[n] and n in reach[m]}
        seen |= comp
        if len(comp) > 1:
            rep = sorted(comp, key=lambda p: (-len(decls_in.get(p, [])), p))[0]
            for m in comp:
                canon[m] = rep
    return canon


def _decl_usage(conn, problem: str, placed, workspace) -> "dict":
    """Decl-level USAGE DAG over `placed` slugs: proof-term citations
    (`inventory.usage_graph`) PLUS Defs-source edges. This is the SINGLE graph
    both the classify CONTEXT (so the agent lays files out along the edges it
    will be judged on) and the pre-commit merged-size GATE are computed from —
    feeding the agent the decomposition DAG (`InvDecl.deps`) instead, as the
    context used to, leaves file-level citation cycles the agent never saw.

    Defs decls have no proofs/L_ files, so `usage_graph` records NO edges among
    them; read their edges from Defs.lean itself (X->Y when Y's name appears as
    a whole token in X's slice) so the toposort can order them (stokes
    form_bundle, 2026-06-11). Defs.lean compiles, so these edges form a sub-DAG
    of source order — no cycle possible from code text."""
    from ...quality.librarian import inventory as _inv
    placed = list(placed)
    usage = _inv.usage_graph(workspace, problem, placed,
                             alias_map=_merge_alias_map(conn, problem),
                             root_source=_root_source(conn, problem, workspace))
    defs_placed = [d for d in placed
                   if d in set(_inv.defs_decls(workspace, problem))]
    if len(defs_placed) > 1:
        dl = db.problem_dir(workspace, problem) / "Defs.lean"
        if dl.exists():
            dtext = dl.read_text(encoding="utf-8")
            code = {d: _code_normalized(_defs_decl_source(dtext, d) or "")
                    for d in defs_placed}
            for x in defs_placed:
                for y in defs_placed:
                    if x != y and re.search(rf"\b{re.escape(y)}\b", code[x]):
                        usage.setdefault(x, set()).add(y)
    return usage


def _plan_usage_and_canon(conn, problem: str, plan: ClassifyPlan,
                          workspace) -> "tuple[dict, dict]":
    """`(usage, canon)` for a layout plan — the ground-truth pieces both the
    pre-commit merged-size gate and `commit_classify` need, computed once.

    `usage` is the decl-level USAGE DAG (`_decl_usage`); `canon` is
    `{file_path: canonical_path}` collapsing each strongly-connected component
    of the FILE-level usage graph (a cyclic file group is an un-splittable
    circular import → one file). Pure: no DB writes, no logging — the caller
    owns the "merging cyclic file" print so it fires only on actual commit."""
    placed = [d for f in plan.files for d in f.decls]
    usage = _decl_usage(conn, problem, placed, workspace)
    # File-level usage graph: file F depends on file G iff a decl in F cites a
    # decl placed in G. Merge cyclic file groups (circular imports) into one.
    decl_file = {d: f.path for f in plan.files for d in f.decls}
    decls_in = {f.path: list(f.decls) for f in plan.files}
    fgraph: dict = {f.path: set() for f in plan.files}
    for d, deps in usage.items():
        fa = decl_file.get(d)
        for dep in deps:
            fb = decl_file.get(dep)
            if fa and fb and fa != fb:
                fgraph[fa].add(fb)
    return usage, _merge_file_sccs(fgraph, decls_in)


def _scc_cross_file_edges(plan: ClassifyPlan, members: "list[str]",
                          usage: "dict | None") -> "list[tuple]":
    """The cross-file proof-term citations AMONG the SCC member files — the
    edges whose two-way presence makes the file group cyclic. Returns one
    example `(decl, file, cited_decl, cited_file)` per directed file-pair,
    bidirectional pairs (the direct `A<->B` cycles) first, so the agent can
    target a few specific declarations to move instead of re-partitioning
    blind."""
    if not usage:
        return []
    member_set = set(members)
    decl_file = {d: f.path for f in plan.files for d in f.decls
                 if f.path in member_set}
    pair_example: dict = {}
    for x, deps in usage.items():
        fx = decl_file.get(x)
        if fx is None:
            continue
        for y in deps:
            fy = decl_file.get(y)
            if fy is not None and fy != fx:
                pair_example.setdefault((fx, fy), (x, y))
    out = []
    for (fa, fb), (x, y) in pair_example.items():
        bidir = (fb, fa) in pair_example
        out.append((bidir, x, fa, y, fb))
    out.sort(key=lambda e: (not e[0], e[2], e[4]))   # bidirectional first
    return [(x, fa, y, fb) for _b, x, fa, y, fb in out]


def verify_merged_file_sizes(plan: ClassifyPlan, canon: dict,
                             decl_lines: dict,
                             usage: "dict | None" = None) -> str:
    """Reject a plan whose files, AFTER the un-splittable-SCC merge
    (`_plan_usage_and_canon`), land a single Lean module over the size budget —
    the per-PLANNED-file check in `verify_classify` misses this because the
    merge runs later (a usage cycle the agent's declared imports don't show:
    residue_thm WindingNumberInteger absorbed 8 files -> 3392 lines, which would
    then STALL forever at the audit zero-warning gate on `longFile`, 2026-06-18).
    The decl usage graph is a DAG, so a cyclic FILE group is the agent's
    grouping artifact — a topological re-partition can break it. When `usage`
    (the decl-level citation graph) is supplied, the message NAMES the specific
    cross-file back-edges so the agent can move a few decls instead of guessing
    where the entanglement is. "" on ok."""
    merged: dict = {}
    for f in plan.files:
        merged.setdefault(canon.get(f.path, f.path), []).extend(f.decls)
    for cf, decls in merged.items():
        est = sum(decl_lines.get(d, 0) for d in decls)
        if est <= CLASSIFY_FILE_LINE_BUDGET:
            continue
        members = sorted(f.path for f in plan.files
                         if canon.get(f.path, f.path) == cf)
        if len(members) > 1:
            edges = _scc_cross_file_edges(plan, members, usage)
            hint = ""
            if edges:
                shown = edges[:12]
                _leaf = lambda p: p.rsplit("/", 1)[-1]  # noqa: E731
                hint = (" The cross-file citations entangling them — move one "
                        "endpoint of each so citations point one way: "
                        + "; ".join(
                            f"`{x}` ({_leaf(fa)}) cites `{y}` ({_leaf(fb)})"
                            for x, fa, y, fb in shown)
                        + ("; …" if len(edges) > len(shown) else "") + ".")
            return (f"files {members} cite each other (a usage cycle) and so "
                    f"MUST share one Lean module, which then runs ~{est} source "
                    f"lines (budget {CLASSIFY_FILE_LINE_BUDGET}; mathlib's "
                    f"longFile caps at 1500). A circular import can't be split, "
                    f"so regroup to break the cycle: order the files along the "
                    f"dependency chain so a file only cites declarations in "
                    f"files it imports (no two files citing into each other), "
                    f"and keep each under budget." + hint)
        # Single oversize file — also caught by verify_classify's per-file pass,
        # repeated here so the post-merge gate is self-contained.
        return (f"{cf}: ~{est} source lines (budget {CLASSIFY_FILE_LINE_BUDGET}; "
                f"mathlib's longFile caps files at 1500) — split it into "
                f"sub-topic files")
    return ""


def commit_classify(conn, problem: str, plan: ClassifyPlan,
                    workspace, *, precomputed: "tuple[dict, dict] | None" = None
                    ) -> None:
    """Persist the layout plan: per decl, its target file + in-file order.
    Only `deduped` (kept) decls advance to `classified`.

    Two corrections to the agent's layout, both driven by the ground-truth
    USAGE DAG (proof-term citations, `inventory.usage_graph`), since the
    agent lays out by meaning but Lean is import-/order-sensitive:
      - files whose decls form a usage cycle are merged into one file (an SCC
        is an un-splittable circular import — `_merge_file_sccs`);
      - within each (possibly merged) file, decls are topologically reordered
        so a cited sibling precedes its user.

    `precomputed` lets the caller pass the `(usage, canon)` it already built for
    the pre-commit merged-size gate, so `usage_graph` is computed once.
    """
    # A fresh classify is a NEW chain attempt: drop any per-file / serial
    # stall counts left over from a PRIOR ingestion of this problem (a library
    # reset + re-run), else `_librarian_refill` skips a still-capped file as
    # "stalled" before the new attempt even runs it — a reverted+re-ingested
    # problem inherited the pre-fix STALL caps and the migrate chain never
    # advanced (residue_thm WindingNumber, 2026-06-17).
    db.clear_librarian_fail_counts_for_problem(conn, problem)
    usage, canon = precomputed if precomputed is not None else \
        _plan_usage_and_canon(conn, problem, plan, workspace)
    from ...quality.librarian import inventory as _inv
    placed = [d for f in plan.files for d in f.decls]
    defs_placed = [d for d in placed
                   if d in set(_inv.defs_decls(workspace, problem))]
    if canon:
        for orig, rep in sorted(canon.items()):
            if orig != rep:
                print(f"[librarian] classify: merging cyclic file {orig} -> "
                      f"{rep} (un-splittable usage SCC)", flush=True)
    # Regroup decls under their canonical file (SCC members merged), keeping
    # the agent's intra-group order before the usage toposort.
    merged: dict = {}
    for f in plan.files:
        merged.setdefault(canon.get(f.path, f.path), []).extend(f.decls)
    defs_set = set(defs_placed)
    for cf, decls in merged.items():
        for order, slug in enumerate(
                _toposort_intra_file(decls, usage, defs_set)):
            db.set_library_classification(
                conn, problem=problem, slug=slug,
                target_file=cf, target_name=None, file_order=order)


# ---------------------------------------------------------------------
# File-level dependency DAG (GAP 2 — reconstructed, no schema column)
# ---------------------------------------------------------------------
# classify computed the cross-file import DAG (ClassifyFile.imports,
# verify_classify checks acyclicity) but commit_classify drops it and
# library_decls has no imports column. migrate needs that DAG to (a) pick
# the next ready file in topological order and (b) tell the agent which
# sibling Library modules it may import. Rebuild it from per-decl deps
# (inventory / tree.py ground truth) + the slug→target_file mapping, so
# no schema migration is needed.


def _merge_alias_map(conn, problem: str) -> "dict[str, str]":
    """Each dedup-`merge` slug → its canonical placed slug, chains resolved
    to the final target. A proof that imports a merged-away sibling's
    `L_<Y>` resolves, in the migrated Library, to this canonical — so the
    usage DAG must remap Y→canonical or it loses the citation edge."""
    raw = {r["slug"]: r["citation"]
           for r in db.library_decls_for(conn, problem)
           if r["verdict"] == "merge" and r["citation"]}
    out: dict[str, str] = {}
    for s in raw:
        seen, cur = {s}, raw[s]
        while cur in raw and cur not in seen:
            seen.add(cur)
            cur = raw[cur]
        out[s] = cur
    return out


def _root_source(conn, problem, workspace) -> "tuple[str, str] | None":
    """(root_slug, abs_path) for the problem's proved root decl, whose proof
    lives in Root.lean (its lean_path), not proofs/L_<slug>.lean — so the
    usage / reference scanners read the root's sibling citations from the
    right file instead of seeing it as dependency-free."""
    r = conn.execute(
        "SELECT slug, lean_path FROM goals WHERE problem = ? "
        "AND origin = 'root' AND status = 'proved' ORDER BY id LIMIT 1",
        (problem,)).fetchone()
    if r and r["lean_path"]:
        return (r["slug"], str(workspace / r["lean_path"]))
    return None
