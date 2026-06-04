---
problem: LinearAlgebra.normal_diagonalization
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.normal_diagonalization — Spectral theorem for normal operators (ℂ)

## Statement
∀ {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V] [FiniteDimensional ℂ V]
  (T : V →ₗ[ℂ] V), Commute (LinearMap.adjoint T) T →
  ∃ e : OrthonormalBasis (Fin (Module.finrank ℂ V)) ℂ V,
    (LinearMap.toMatrix e.toBasis e.toBasis T).IsDiag

## Setting
- `V` finite-dimensional complex inner-product space.
- `T` a **normal** operator: it commutes with its adjoint
  (`Commute (LinearMap.adjoint T) T`, i.e. `T† ∘ T = T ∘ T†`).
- Conclusion: there is an **orthonormal** basis `e` of `V` in which the matrix of
  `T` is diagonal. This is the complex spectral theorem for normal operators —
  the generalization of the Hermitian/self-adjoint case to all normal operators.

mathlib has the self-adjoint spectral theorem (`Matrix.IsHermitian.spectral_theorem`
and operator forms) but **not** the general normal version (mathlib gaps catalog #12:
`Matrix.IsNormal.diagonal` 0 hit).

## Lemma hints

Likely relevant — **confirm with Grep/Loogle before reconstructing (R1)**:

- `Library.LinearAlgebra.SchurTriangularization.Triangularization.main` — **our Library
  Schur theorem** (algebraic, any algebraically closed field): every endomorphism has a
  basis in which its matrix is `BlockTriangular id` (upper triangular). ℂ is algebraically
  closed, so this applies to `T`. **Cite it for the triangularization step.**
- `Mathlib/Analysis/InnerProductSpace/GramSchmidtOrtho.lean` —
  `gramSchmidtOrthonormalBasis`, `gramSchmidt` (orthonormalize a basis; Gram-Schmidt
  preserves the partial-sum spans, so an upper-triangular flag stays upper-triangular in
  the resulting orthonormal basis).
- `Mathlib/Analysis/InnerProductSpace/Adjoint.lean` — `LinearMap.adjoint` and its
  characterizing inner-product identity.
- `Mathlib/LinearAlgebra/Matrix/IsDiag.lean` — `Matrix.IsDiag`.
- `Mathlib/Analysis/InnerProductSpace/PiL2.lean` — `OrthonormalBasis`, `.toBasis`,
  `LinearMap.toMatrix` in an orthonormal basis.

## Strategic notes

Standard textbook route (Schur ⇒ spectral), reusing our Library:

1. **Triangularize via Library Schur**: cite
   `Library.LinearAlgebra.SchurTriangularization.Triangularization.main` to get a basis in
   which `T` is upper triangular (the invariant flag). ℂ is `IsAlgClosed`.
2. **Orthonormalize keeping the flag**: Gram-Schmidt that basis to an orthonormal basis
   `e`. Because Gram-Schmidt preserves each initial-segment span, the flag is preserved, so
   `toMatrix e e T` is still upper triangular.
3. **Normal + upper-triangular ⇒ diagonal**: an upper-triangular matrix `M` (in an
   orthonormal basis, so `Mᴴ` is the adjoint's matrix) with `Commute Mᴴ M` is diagonal —
   compare diagonal entries of `M Mᴴ` and `Mᴴ M` row by row (induction on the column).

Let the Backward agent commit to its angle; the Schur-citation + Gram-Schmidt skeleton
above is the suggested decomposition but not mandatory.

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def`: `Grep` mathlib (and `Library/`) + `loogle` for
the result; reuse and write a thin bridge if it exists. A `## Forward rationale` first line
must read `Grep + Loogle confirmed missing` with the exact keywords. In particular, if
mathlib already states the **normal** spectral theorem under some name, surface it via
`RequestUserAmend` — the problem is then already done.

### Forbidden angles

- Reconstructing Schur from scratch — cite the Library entry above.
- Reconstructing Gram-Schmidt — it is in mathlib.
