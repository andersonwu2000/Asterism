import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_block_diag
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_conj_matrix
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_intertwine_x

namespace Problems.LinearAlgebra.rational_canonical_form

-- Transport-only assembly: conjugate `T` through the K-linear equiv
--   `g = (AEval'.of T) ≫ (e.restrictScalars K) : V ≃ₗ[K] ⨁ᵢ K[X]/(fᵢ)`,
-- and read off the block-diagonal matrix in the transported power basis `c`.
-- `intertwine_x` : `g` carries `T` to the `K[X]`-scalar action `X • ·` (= `S`)
--   (via `AEval'.X_smul_of` + `e`'s `K[X]`-linearity) — no matrices.
-- `conj_matrix`  : abstract conjugation lemma — `toMatrix (c.map g.symm) _ T = toMatrix c c S`.
-- `block_diag`   : the `X`-action on the direct sum is `blockDiagonal'` of the per-block
--   `mulLeft K (root fᵢ)` matrices (the internal-direct-sum / DFinsupp.basis computation).
-- Combine by `rw [hconj, hblock]`. Each piece drops either `T`/`e` (block_diag) or the
--   rational-canonical-form specifics (conj_matrix), so all three are strictly simpler.
theorem s11593 {K : Type*} [Field K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V) {r : ℕ} (f : Fin r → Polynomial K)
    (hmonic : ∀ i, (f i).Monic)
    (e : Module.AEval' T ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i})) :
    ∃ b : Module.Basis (Σ i : Fin r, Fin (f i).natDegree) K V,
      LinearMap.toMatrix b b T
        = Matrix.blockDiagonal' (fun i =>
            LinearMap.toMatrix (AdjoinRoot.powerBasis' (hmonic i)).basis
              (AdjoinRoot.powerBasis' (hmonic i)).basis
              (LinearMap.mulLeft K (AdjoinRoot.root (f i))))  := by
  classical
  set g : V ≃ₗ[K] DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}) :=
    (Module.AEval'.of T).trans (e.restrictScalars K) with hg
  set c : Module.Basis (Σ i : Fin r, Fin (f i).natDegree) K
      (DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i})) :=
    DFinsupp.basis (fun i => (AdjoinRoot.powerBasis' (hmonic i)).basis) with hc
  set S : DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}) →ₗ[K]
          DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}) :=
    (LinearMap.lsmul (Polynomial K) _ Polynomial.X).restrictScalars K with hS
  refine ⟨c.map g.symm, ?_⟩
  have hint : ∀ v : V, g (T v) = S (g v) := by
    rw [hg, hS]; exact intertwine_x T f e
  have hconj : LinearMap.toMatrix (c.map g.symm) (c.map g.symm) T
      = LinearMap.toMatrix c c S := conj_matrix g c T S hint
  have hblock : LinearMap.toMatrix c c S
      = Matrix.blockDiagonal' (fun i =>
          LinearMap.toMatrix (AdjoinRoot.powerBasis' (hmonic i)).basis
            (AdjoinRoot.powerBasis' (hmonic i)).basis
            (LinearMap.mulLeft K (AdjoinRoot.root (f i)))) := by
    rw [hc, hS]; exact block_diag f hmonic
  rw [hconj, hblock]


end Problems.LinearAlgebra.rational_canonical_form
