import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- Direct leaf: the Rayleigh set is nonempty because e_k = eigenvectorBasis k
-- is a nonzero element of S (k ≤ k puts it in the spanning image set), so its
-- Rayleigh quotient is a member. No sub-goals needed.
theorem s11628
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n)
    (S : Submodule ℝ E)
    (hS : S = Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {i : Fin n | (i : ℕ) ≤ (k : ℕ)})) :
    (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
      q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2).Nonempty  := by
  refine ⟨_, (hT.eigenvectorBasis hn) k, ?_, ?_, rfl⟩
  · rw [hS]
    apply Submodule.subset_span
    exact ⟨k, by simp, rfl⟩
  · exact (hT.eigenvectorBasis hn).toBasis.ne_zero k

end Problems.LinearAlgebra.courant_fischer
