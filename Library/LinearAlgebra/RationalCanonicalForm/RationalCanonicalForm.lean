import Library.LinearAlgebra.InvariantFactor.InvariantFactorDecomposition
import Library.LinearAlgebra.RationalCanonicalForm.CompanionMatrix
import Library.LinearAlgebra.RationalCanonicalForm.DirectSumDecomp
import Mathlib

open Library.LinearAlgebra.RationalCanonicalForm.CompanionMatrix
open Library.LinearAlgebra.RationalCanonicalForm.DirectSumDecomp

namespace Library.LinearAlgebra.RationalCanonicalForm.RationalCanonicalForm

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
theorem block_assembly {K : Type*} [Field K]
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

-- Split assembly (basis transport) from per-block companion identification.
-- `block_assembly` builds the K-basis (DFinsupp of per-block power bases, transported
--   through `e` and `Module.AEval'.of T`) and shows `toMatrix b b T` is the block diagonal
--   of the per-block "multiply by root" operator matrices — pure functorial transport, no
--   polynomial arithmetic.
-- `block_companion` identifies each per-block operator matrix with `companionMatrix (f i)`
--   (the %ₘ-coefficient computation), so the two pieces are strictly simpler than the parent.
-- Combine: rewrite by `block_assembly`, then `congr`/`funext` and discharge each block by
--   `block_companion`.
theorem companion_block_basis {K : Type*} [Field K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V) {r : ℕ} (f : Fin r → Polynomial K)
    (hmonic : ∀ i, (f i).Monic)
    (e : Module.AEval' T ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i})) :
    ∃ b : Module.Basis (Σ i : Fin r, Fin (f i).natDegree) K V,
      LinearMap.toMatrix b b T
        = Matrix.blockDiagonal' (fun i => companionMatrix (f i))  := by
  obtain ⟨b, hb⟩ := block_assembly T f hmonic e
  refine ⟨b, ?_⟩
  rw [hb]
  congr 1
  funext i
  exact block_companion (hmonic i)

-- Obtain the invariant factors `f` + the K[X]-linear iso `e` to the cyclic direct
-- sum from the Library (Manifest steps 0-1), then delegate the K-basis + companion
-- block-diagonal matrix assembly (steps 2-3) to `companion_block_basis`, which takes
-- `e` as a hypothesis so the PID/CRT existence work is already discharged.
theorem main : ∀ {K : Type*} [Field K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ (r : ℕ) (f : Fin r → Polynomial K),
    (∀ i, (f i).Monic) ∧
    (∀ i, ¬ IsUnit (f i)) ∧
    (∀ i j, i ≤ j → f i ∣ f j) ∧
    ∃ b : Module.Basis (Σ i : Fin r, Fin (f i).natDegree) K V,
      LinearMap.toMatrix b b T
        = Matrix.blockDiagonal' (fun i => companionMatrix (f i))  := by
  intro K _ V _ _ _ T
  obtain ⟨r, f, hmonic, hnonunit, hdvd, ⟨e⟩⟩ :=
    Library.LinearAlgebra.InvariantFactor.InvariantFactorDecomposition.main T
  have h_assembly := companion_block_basis T f hmonic e
  exact ⟨r, f, hmonic, hnonunit, hdvd, h_assembly⟩

end Library.LinearAlgebra.RationalCanonicalForm.RationalCanonicalForm
