---
problem: LinearAlgebra.schur_triangularization
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.schur_triangularization — Schur upper-triangularization (algebraic form)

## Statement
∀ {K : Type*} [Field K] [IsAlgClosed K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
    (LinearMap.toMatrix b b T).BlockTriangular id

## Setting
- `K` algebraically closed field (e.g. `ℂ`)
- `V` finite-dim `K`-vector space
- `T` arbitrary `K`-linear endomorphism of `V`
- Conclusion: there is a basis `b` indexed by `Fin (finrank K V)` whose matrix of `T` is
  upper triangular. We encode "upper triangular" as `Matrix.BlockTriangular M id`, which on a
  matrix indexed by `Fin n` with the identity ordering reduces to the standard definition
  (`M i j = 0` whenever `j < i`).

This is the algebraic Schur form; no inner product, no orthonormality. Holds over any
algebraically closed field; the inner-product / unitary variant on `ℂ` would be a stronger
follow-up.

## Lemma hints

Likely relevant mathlib modules:

- `Mathlib/LinearAlgebra/Eigenspace/` — eigenvalue / generalized eigenspace machinery,
  including `Module.End.exists_eigenvalue` (algebraically closed + finite-dim) and
  `Module.End.iSup_maxGenEigenspace_eq_top`.
- `Mathlib/LinearAlgebra/Matrix/Block.lean` — `Matrix.BlockTriangular` definition + lemmas.
- `Mathlib/LinearAlgebra/Matrix/ToLin.lean` — `LinearMap.toMatrix` two-way correspondence.
- `Mathlib/LinearAlgebra/Quotient/Basic.lean` and `Mathlib/LinearAlgebra/Isomorphisms.lean`
  — quotient module + `Submodule.mapQ` for restricting an endomorphism to a quotient.
- `Mathlib/LinearAlgebra/Basis/` — basis construction, extending an independent set to a basis.
- `Mathlib/FieldTheory/IsAlgClosed/Spectrum.lean` — `IsAlgClosed` typeclass hooks.

R1 (Strategic notes below) applies — confirm with `Grep` / Loogle before deciding a lemma is
missing.

## Strategic notes

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
