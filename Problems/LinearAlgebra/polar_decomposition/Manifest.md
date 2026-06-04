---
problem: LinearAlgebra.polar_decomposition
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.polar_decomposition — Polar decomposition of an endomorphism

## Statement
∀ {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E),
  ∃ (U P : E →ₗ[𝕜] E),
    P.IsPositive ∧
    (∀ x, ‖U x‖ = ‖x‖) ∧
    T = U ∘ₗ P

## Setting
- `𝕜 ∈ {ℝ, ℂ}` (`RCLike 𝕜`)
- `E` finite-dim `𝕜`-inner product space
- `T : E →ₗ[𝕜] E` arbitrary endomorphism
- Conclusion: `T = U ∘ₗ P` where
  - `P` is positive self-adjoint (`P = |T| = √(T† ∘ T)` canonically)
  - `U` is an **isometry** (`∀ x, ‖U x‖ = ‖x‖`). In finite dimension `E → E` a linear
    isometry is automatically surjective, i.e. unitary; this is the standard textbook
    statement of polar decomposition. (The partial-isometry-only weakening is *not* used
    here — over a square space `U` can always be completed to a full isometry, since
    `(range |T|)ᗮ = ker T` and `(range T)ᗮ` have equal dimension.)

## Route — derive from the Library SVD (primary, recommended)

This problem is now proved as a short corollary of the **already-Library-ized SVD**. The
spectral / positive-square-root machinery must NOT be rebuilt — cite SVD.

The clean finite-dim derivation (specialise the SVD lemmas at `F := E`, so
`finrank 𝕜 F = finrank 𝕜 E = n` and every `(i : ℕ) < finrank 𝕜 F` side-condition is
automatic):

1. From `Library.LinearAlgebra.SVD.AdjointSelf.eigenbasis_t_adjoint_t T` obtain an
   orthonormal basis `b_E : OrthonormalBasis (Fin n) 𝕜 E` with
   `(T.adjoint ∘ₗ T) (b_E i) = ((σ i)^2 : 𝕜) • b_E i`, where `σ i := T.singularValues i`.
2. Feed that eigen-relation into
   `Library.LinearAlgebra.SVD.BasisConstruction.inner_t_eigenbasis_sq_diag` (to get the
   inner-product diagonal hypothesis `h_inner`) and then
   `Library.LinearAlgebra.SVD.BasisConstruction.b_f_apply_eq_dite` to obtain an orthonormal
   basis `b_F` with `T (b_E i) = (σ i : 𝕜) • b_F i` (the `dite` collapses to this when
   `F = E` because `(i : ℕ) < n` always holds; the `h_zero` premise is vacuous for the same
   reason).
3. Define the two endomorphisms by their action on the orthonormal basis `b_E`
   (`OrthonormalBasis.constr` / `Basis.constr`, or via `b_E.repr`):
   - `P : E →ₗ[𝕜] E` with `P (b_E i) = (σ i : 𝕜) • b_E i`  (diagonal, real nonneg entries).
   - `U : E →ₗ[𝕜] E` with `U (b_E i) = b_F i`  (sends one orthonormal basis to another).
4. Discharge the three conjuncts:
   - `P.IsPositive`: `P` is self-adjoint with `⟨P x, x⟩ = Σ σ i · |⟨x, b_E i⟩|² ≥ 0` (uses
     `σ i ≥ 0`; singular values are nonnegative — Grep mathlib for `singularValues_nonneg`).
   - `∀ x, ‖U x‖ = ‖x‖`: `U` carries the orthonormal basis `b_E` to the orthonormal basis
     `b_F`, hence is a linear isometry (`OrthonormalBasis`/`Orthonormal` norm-preservation;
     expand `x = Σ ⟨x,b_E i⟩ • b_E i` and use Parseval on both sides).
   - `T = U ∘ₗ P`: check on the basis — `(U ∘ₗ P) (b_E i) = U ((σ i) • b_E i)
     = (σ i) • b_F i = T (b_E i)` (step 2); conclude by `Basis.ext` / `b_E.toBasis.ext`.

Alternative (heavier): cite the top-level `Library.LinearAlgebra.SVD.Basic.main` (matrix
form `toMatrix b_E b_F T = diag σ`) and convert matrix→operator. The operator-form lemmas in
step 1–2 are usually less friction than going through `toMatrix`.

## Lemma hints (Library SVD — cite, do not reconstruct)

- `Library.LinearAlgebra.SVD.AdjointSelf.eigenbasis_t_adjoint_t` — `∃ b_E`, the orthonormal
  eigenbasis of `T† ∘ T` with eigenvalues `(σ i)²`.
- `Library.LinearAlgebra.SVD.AdjointSelf.t_adjoint_t_is_symmetric` — `(T† ∘ T).IsSymmetric`.
- `Library.LinearAlgebra.SVD.BasisConstruction.inner_t_eigenbasis_sq_diag` — turns the
  eigen-relation into `⟨T (b_E i), T (b_E j)⟩ = if i=j then (σ i)² else 0`.
- `Library.LinearAlgebra.SVD.BasisConstruction.b_f_apply_eq_dite` /
  `…exists_b_f_apply_eq_dite_with_zero` — `∃ b_F`, `T (b_E i) = σ i • b_F i` (dite form).
- `Library.LinearAlgebra.SVD.Basic.main` — full SVD in matrix-diagonal form (fallback route).

Mathlib (foundational — use directly):
- `LinearMap.singularValues`, `singularValues_nonneg` (verify name via Grep).
- `OrthonormalBasis`, `OrthonormalBasis.constr`/`Basis.constr`, `Basis.ext`,
  `OrthonormalBasis.sum_inner_mul_inner` / Parseval, `LinearMap.IsPositive`.

## R1 — search before reconstructing (hard rule)

Before introducing any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the name/shape you intend to
   build. Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match or near-match exists: reuse it; write a thin bridge lemma. **Do not rebuild
   the spectral theorem, positive square root, SVD, or orthonormal-basis machinery — the
   Library SVD already provides them.**
4. Only after confirmed missing, inject a new Forward whose `## Forward rationale` first line
   states `Grep + Loogle confirmed missing` with the searched keywords.

## Forbidden angles

- **Reconstructing** the positive square root `√(T†T)`, the spectral theorem, or any SVD
  internal — cite `Library.LinearAlgebra.SVD.*` instead. Rebuilding them is the exact
  duplication this re-derivation exists to eliminate.
- Citing the entire result as a single mathlib theorem if you find one — surface via
  `RequestUserAmend` (the problem is then done).
