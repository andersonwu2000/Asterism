# LinearAlgebra.cholesky_decomposition — BRIEF

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
Two reasonable proof routes (agents' choice):

1. **Reduce to LDL**: cite mathlib's existing `LDL.lower` + `LDL.diag`, take the
   positive square root of `D` (diagonal entries are positive for `PosDef`), absorb
   into `L`. Smallest scope, leans heaviest on existing mathlib infrastructure.
2. **Spectral construction**: diagonalise `A` via the symmetric spectral theorem,
   take `√` on the eigenvalue diagonal, construct `L` from the eigenbasis. More
   self-contained but reconstructs work mathlib already has.

Route 1 is preferred unless mathlib's LDL exposes only `L⁻¹` (then absorbing the
square root may need a small inversion step).

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the type / functor / theorem
   name you intend to build, plus synonym variants. Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match or near-match exists: **reuse it; write a thin bridge lemma** to this
   problem's naming. Do not reconstruct any foundational layer (LDL, positive square
   root on diagonal matrices, spectral theorem, etc.).
4. Only after confirmed missing, inject a new Forward. The `## Forward rationale` first
   line must state `Grep + Loogle confirmed missing` and list the exact keywords
   searched.

Strategist: when a Forward output is an obvious mathlib candidate that the agent did
not `Grep`, `ConfirmShelve` it and re-inject a Forward requiring the search step first.

### Forbidden angles

- Building Cholesky from scratch via Gram-Schmidt orthogonalisation when LDL is
  already in mathlib (Route 1 is the smaller scope).
- Citing the entire result as a single mathlib theorem if you find one (surface via
  `RequestUserAmend`).
