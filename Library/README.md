# Library/

Cross-Problem reusable lemma store. When a Problem's root is proved **and**
`integrity_verified=1`, and its `Manifest.md` frontmatter has
`library: true`, the **Librarian** migrates that Problem's proof forest
into here — organized Mathlib-style by topic — so later Problems can
`import` and cite the lemmas it produced.

> The old auto-promote hook (a `theorem <problem> := Problems.<problem>.main`
> re-export written on `status='proved'`) was **removed**. Library-ization
> now runs entirely through the Librarian chain. Design: see
> `docs/archive/design/librarian_plan.md` (v0.3 mechanical core) +
> `librarian_cleanup.md` (v0.4 cleanup campaign).

## How it is populated

The Librarian runs **per file** as a dispatcher work-kind (gated on
`integrity_verified=1` + `library: true`), advancing each declaration
through `library_decls.lifecycle`:

```
dedup → classify → migrate → cleanup → bridge
lifecycle: candidate → deduped → classified → migrated → cleaned
           (terminal-but-unplaced: dropped / cited)
```

- **migrate** is a faithful **mechanical relabel** of `Problems.<p>.*`
  namespaces into `Library.<Topic>.*` — it moves full declaration bodies,
  **not** re-exports. Most files migrate with no LLM.
- **classify** (LLM) decides which Mathlib-style topic + file each decl lands in.
- **cleanup** (LLM) polishes toward mathlib-PR-ready.
- **bridge** finalizes and writes the INDEX section.

## Structure

```
Library/
  <Topic>/<Subtopic>/<File>.lean   # migrated decl forest — many files per Problem
  INDEX.md                          # single root-level index of every placed decl
```

`INDEX.md` is **one file** at `Library/INDEX.md` (not per-topic), written by
`librarian._write_library_index`; it lists each placed declaration's full
name and target file, grouped by source Problem. Topics currently in use:
`Analysis/`, `Geometry/`, `LinearAlgebra/`, `Logic/` (the `classify` stage
picks the closest Mathlib first-level topic per Problem).

Files here are **Librarian-managed** — don't hand-edit; the next chain run
overwrites. During active development the whole `Library/` tree is
**dev-scratch**, not a stable artifact. `asterism library-verify` checks
whole-Library coherence (`lake build Library` + INDEX↔disk↔DB consistency).

## Referencing in a Problem's Manifest

Relevant Library / Mathlib lemmas are found automatically by the per-node
**pre-search** (target-1): before each goal is dispatched, a search agent
surfaces likely-relevant lemmas (Mathlib + Library + in-problem) and injects a
ranked, `#check`-verified `## Candidate lemmas` section into the prover's
Context. The dedicated `## Lemma hints` Manifest section was retired in favour
of this.

To *force* a specific pointer the pre-search might miss, mention the
fully-qualified name (`Library.<Topic>…<decl>`, exactly as in
`Library/INDEX.md`) in the Manifest's **`## Strategic notes`** — the prover
reads that section directly.
