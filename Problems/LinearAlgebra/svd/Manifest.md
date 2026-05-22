---
problem: LinearAlgebra.svd
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.svd — Singular value decomposition (factorization theorem)

## Statement
∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F),
  ∃ (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
    (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    LinearMap.toMatrix b_E.toBasis b_F.toBasis T =
      Matrix.of (fun (j : Fin (Module.finrank 𝕜 F)) (i : Fin (Module.finrank 𝕜 E)) =>
        if (j : ℕ) = (i : ℕ)
        then ((T.singularValues i : ℝ) : 𝕜)
        else 0)

## Setting
- `𝕜 ∈ {ℝ, ℂ}` (`RCLike 𝕜`)
- `E, F` finite-dim `𝕜`-inner product spaces (rectangular case: `dim E ≠ dim F` allowed)
- `T : E →ₗ[𝕜] F` arbitrary linear map
- Conclusion: there exist orthonormal bases `b_E` of `E` and `b_F` of `F` such that in those
  bases, `T`'s matrix is "diagonal" with the singular values on the diagonal entries
  `(j = i)` and zeros elsewhere. Rectangular case: when `dim E ≠ dim F`, the matrix is
  non-square and the diagonal predicate `(j : ℕ) = (i : ℕ)` picks the entries where both
  indices coincide as natural numbers — the "leading diagonal" of the rectangular matrix.
- `T.singularValues` is the existing mathlib function (`Mathlib.Analysis.InnerProductSpace.SingularValues`).

## Lemma hints

Likely relevant mathlib modules:

- `Mathlib/Analysis/InnerProductSpace/SingularValues.lean` — the `singularValues` function
  (`ℕ →₀ ℝ`), `support_singularValues`, `singularValues_antitone`,
  `sq_singularValues_fin`, `hasEigenvalue_adjoint_comp_self_sq_singularValues`.
- `Mathlib/Analysis/InnerProductSpace/Spectrum.lean` — `IsSymmetric.eigenvectorBasis`,
  `IsSymmetric.diagonalization`. Use on `T.adjoint ∘ₗ T` (positive self-adjoint).
- `Mathlib/Analysis/InnerProductSpace/Positive.lean` — `IsPositive`,
  `IsPositive.nonneg_eigenvalues`.
- `Mathlib/Analysis/InnerProductSpace/Adjoint.lean` — `LinearMap.adjoint`.
- `Mathlib/Analysis/InnerProductSpace/Basic.lean` — `OrthonormalBasis`, extension /
  reindexing utilities.
- `Mathlib/LinearAlgebra/Matrix/ToLin.lean` — `LinearMap.toMatrix`.

## Strategic notes

Standard textbook proof skeleton (agents may follow or deviate):

1. `T† ∘ T : E →ₗ[𝕜] E` is positive self-adjoint.
2. Apply `IsSymmetric.eigenvectorBasis` (or similar) to obtain an orthonormal basis `b_E` of
   `E` diagonalising `T† ∘ T` with eigenvalues `λ_i = (singularValues T i)²`.
3. For the indices `i` where `λ_i > 0` (equivalently `i < rank T`), define
   `u_i := T(b_E i) / σ_i` (where `σ_i := singularValues T i`). Verify `{u_i}` is
   orthonormal in `F`.
4. Extend `{u_i}_{i < rank T}` to an orthonormal basis `b_F` of `F` (any orthonormal
   completion; mathlib has helpers for this).
5. In bases `(b_E, b_F)`, verify the matrix is diagonal with `σ_i` entries.

Proof angle is the agents' choice. The above is one route; alternatives include going via
`PosPart` / continuous functional calculus, or constructing the basis pair via the joint
diagonalisation of `T† ∘ T` and `T ∘ T†`.

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the type / functor / theorem
   name you intend to build, plus synonym variants. Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match or near-match exists: **reuse it; write a thin bridge lemma** to this
   problem's naming. Do not reconstruct any foundational layer (singular values, spectral
   theorem, orthonormal basis machinery, adjoint, etc.).
4. Only after confirmed missing, inject a new Forward. The `## Forward rationale` first
   line must state `Grep + Loogle confirmed missing` and list the exact keywords searched.

Strategist: when a Forward output is an obvious mathlib candidate that the agent did not
`Grep`, `ConfirmShelve` it and re-inject a Forward requiring the search step first.

### Forbidden angles

- Citing Jordan normal form / polar decomposition (mathlib lacks them; would be circular
  side quests).
- Citing the entire result as a single mathlib theorem if you find one (surface via
  `RequestUserAmend` — the problem is then done).
