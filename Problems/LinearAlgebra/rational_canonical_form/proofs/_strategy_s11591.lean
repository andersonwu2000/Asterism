import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Library.LinearAlgebra.InvariantFactor.InvariantFactorDecomposition
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_companion_block_basis

namespace Problems.LinearAlgebra.rational_canonical_form

-- Obtain the invariant factors `f` + the K[X]-linear iso `e` to the cyclic direct
-- sum from the Library (Manifest steps 0-1), then delegate the K-basis + companion
-- block-diagonal matrix assembly (steps 2-3) to `companion_block_basis`, which takes
-- `e` as a hypothesis so the PID/CRT existence work is already discharged.
theorem s11591 : ∀ {K : Type*} [Field K]
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

end Problems.LinearAlgebra.rational_canonical_form
