# Asterism Library Blueprint — ARCHIVED 2026-08-26

> Retired. The idea — re-tell the machine's formalized proofs as
> readable mathematics with a clickable dependency graph — shipped
> instead as the console's **Library Atlas** (`web/src/screens/Library.tsx`,
> which names this experiment as its ancestor), where the graph is live
> against the DB rather than regenerated from a LaTeX build.
>
> What is kept here is the part that would be expensive to work out
> again: the generator (`gen/`, Lean decl dump → `content.tex`), the
> build script, the hand-curated 8-node exposition
> (`content.manual.tex`), and the Windows/zh-TW gotchas below. The
> generated output, the screenshots and the 154 MB `.venv` are gone;
> `blueprint/` no longer exists in the working tree. `residue_deps.json`
> (a June snapshot of `Library/Analysis/ResidueTheorem/`) went with
> them — regenerate it with `gen/DumpResidueDeps.lean` if it is ever
> wanted, since the subtree has been re-harvested since.
>
> Paths below are written as they were when this lived at `blueprint/`.



A [leanblueprint](https://github.com/PatrickMassot/leanblueprint) document that re-tells the
machine-formalized proofs in `Library/` as human-readable mathematics, with a clickable
dependency graph linking each statement to its Lean declaration.

Everything the plugin needs lives under `blueprint/` (Python tool in `.venv/`, sources in
`src/`, generated output in `web/` and `print/`). Nothing outside `blueprint/` is required to
build, except the system tools listed below.

## Current scope

The **Residue Theorem** subtree harvested into `Library/Analysis/ResidueTheorem/`.

`src/content.tex` is **auto-generated** by the generator below (33 nodes: the two defs +
one principal theorem per source file, 66 citation edges, all `\leanok`). A hand-written,
curated 8-node version is kept for comparison at `src/content.manual.tex` (swap it in by
copying over `src/content.tex` if you prefer the tighter exposition).

## Build

```powershell
powershell -File blueprint/build.ps1          # web (HTML + dependency graph)
powershell -File blueprint/build.ps1 -Serve   # build, then http://localhost:8000
```

Then open `blueprint/web/index.html` (exposition) and `blueprint/web/dep_graph_document.html`
(dependency graph). The graph SVG is inlined, so `file://` works; MathJax pulls from a CDN, so
math needs internet (or use `-Serve`).

## Prerequisites (one-time)

System-level tools (cannot be contained in `blueprint/`, like TeX itself):

- **Python** + the contained venv: `python -m venv blueprint/.venv` then
  `blueprint/.venv/Scripts/python -m pip install leanblueprint`.
- **graphviz** (for the dependency graph): `scoop install graphviz`.
- **TeX** (only for the optional PDF): TinyTeX/xelatex, already present here.

## Windows gotchas (already handled in `build.ps1`)

Discovered while bringing this up on a zh-TW Windows box; recorded so they don't bite again:

1. **`UnicodeDecodeError: 'cp950' codec ...`** — plastex `open()`s its UTF-8 `.sty`/templates
   with the system locale (cp950) and chokes. Fix: `PYTHONUTF8=1`.
2. **dependency graph fails with an empty `OSError` from `tred`/`dot`** — pygraphviz pipes the
   graph through the graphviz CLI, but the **scoop shim** for `dot`/`tred` does not forward the
   piped stdin/stdout (made worse by `CREATE_NO_WINDOW`), so the program reads nothing and emits
   nothing. Fix: put the **real** graphviz bin (`~/scoop/apps/graphviz/current/bin`) ahead of the
   scoop shim on `PATH`.

## Deliberately NOT set up (to keep the footprint inside `blueprint/`)

- **`leanblueprint new`** — interactive, and it scatters a `.github/workflows/blueprint.yml`
  and edits the root `lakefile`. We scaffolded `src/` by hand instead.
- **`checkdecls`** — would add `require checkdecls` to the root `lakefile.lean`. To verify the
  `\lean{}` names against the built Lean, add it and run `lake build` + `leanblueprint checkdecls`.
- **doc-gen4 / CI deploy to GitHub Pages** — separate follow-ups.

## Regenerating from the Library (the Asterism generator)

`src/content.tex` is produced from the Library itself in two stages — run from the repo root:

```bash
lake env lean blueprint/gen/DumpResidueDeps.lean         # 1. Lean env  -> gen/residue_deps.json
blueprint/.venv/Scripts/python.exe blueprint/gen/gen_content.py   # 2. json + sources -> src/content.tex
```

1. **`gen/DumpResidueDeps.lean`** walks the Lean *environment* and dumps, for every
   declaration under `Library.Analysis.ResidueTheorem` (plus the two `Complex` defs), its
   fully-qualified name, kind, and docstring → `gen/residue_deps.json`.
2. **`gen/gen_content.py`** turns that into the blueprint: one node per source file's
   principal theorem (plus the defs), docstrings as the prose, and `\uses` edges.

### Why edges come from a source scan, not the environment

`lake env lean` does **not** load imported theorem *proof bodies* (`ConstantInfo.value?` is
`none` even for `Nat.add_comm`), so the proof-level dependency edges are not recoverable from
the environment. The generator therefore reads the citation edges by scanning the `.lean`
sources for declaration names. Definitions are treated as foundational sinks (no out-edges)
to avoid co-location false cycles.

### Note on `Library/INDEX.md`

The generator does **not** read `Library/INDEX.md` (machine-only, and may be retired). All
data comes from the Lean environment + the `.lean` sources. This is called out in the headers
of `DumpResidueDeps.lean`, `gen_content.py`, and the generated `content.tex`.

### Known rough edges (PoC)

- Granularity is one principal theorem per file (33 nodes = the whole subtree), not curated
  down to a handful of keystones. A keystone filter (e.g. only cross-file-cited results) would
  shrink the graph.
- Edges are heuristic whole-word name matches; usually right, occasionally over-connects.
- Docstrings are transcribed Lean-markdown: backtick `code` → `\texttt{}` and `$math$` is kept
  verbatim, but heavily-marked-up docstrings can still read roughly.
