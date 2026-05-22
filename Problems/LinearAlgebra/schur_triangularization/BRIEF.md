# LinearAlgebra.schur_triangularization — BRIEF

_Auto-rendered from `Manifest.md` + `Library/`. The framework_
_inlines this file into `Context.md` for every Builder /_
_Backward dispatch on this problem._

## Sandbox
- Reads allowed without permission prompts:
  - This goal's problem dir (your cwd).
  - `.lake/packages/mathlib/Mathlib/` for `rg`/`Read` on Mathlib source.
- Reads NOT allowed: other `Problems/<...>/` dirs — irrelevant to this goal. Use Loogle / Grep on Mathlib instead.
- `Context.md` + `PAST_*.md` companion files: read-only.
- `patch.lean` is your single output. Lead with `--` annotation comments, then edit the body (Builder fills in the proof; Backward edits the strategy skeleton's body — signature locked). See the kind-specific prompt for layout.

## Strategic notes (from Manifest.md)
The proof method is the agents' choice. Standard textbook routes include:

- Induction on `finrank K V`: extract an eigenvalue, take its 1-dim invariant subspace,
  apply the inductive hypothesis to the quotient endomorphism.
- Routing through the existing `iSup_maxGenEigenspace_eq_top`: build a basis adapted to the
  generalized-eigenspace decomposition, then refine within each block by the
  nilpotent-kernel filtration.

Strategist should let the Backward agent commit to its chosen angle.

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the type / functor / theorem
   name you intend to build, plus synonym variants. Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match or near-match exists: **reuse it; write a thin bridge lemma** to this problem's
   naming. Do not reconstruct any foundational layer (eigenspace machinery, matrix
   representations, basis manipulation, etc.).
4. Only after confirmed missing, inject a new Forward. The `## Forward rationale` first line
   must state `Grep + Loogle confirmed missing` and list the exact keywords searched.

Strategist: when a Forward output is an obvious mathlib candidate that the agent did not
`Grep`, `ConfirmShelve` it and re-inject a Forward requiring the search step first.

### Forbidden angles

- Citing Jordan normal form to prove Schur. Mathlib lacks Jordan; building it would be a
  multi-week side quest larger than this problem.
- Citing a result that is itself stated as "Schur upper triangular" under a different name
  (if you find one, the problem is already done — surface it via `RequestUserAmend`).
