import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- Termwise weighted-sum bound: distribute λ_k over the sum, then compare term by term.
-- Each term λ_k·rᵢ² ≤ λᵢ·rᵢ²: for i ≤ k the antitone (decreasing) spectrum gives λ_k ≤ λᵢ
-- and rᵢ² ≥ 0; for k < i the high mode vanishes (hv), making both sides 0.
-- Direct (sorry-free) leaf proof: Finset.mul_sum + Finset.sum_le_sum, no sub-goals.
theorem s11635
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) (x : E)
    (hv : ∀ i : Fin n, (k : ℕ) < (i : ℕ) →
      (hT.eigenvectorBasis hn).repr x i = 0) :
    hT.eigenvalues hn k * (∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2)
      ≤ ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2  := by
  rw [Finset.mul_sum]
  apply Finset.sum_le_sum
  intro i _
  by_cases h : (i : ℕ) ≤ (k : ℕ)
  · apply mul_le_mul_of_nonneg_right
    · exact hT.eigenvalues_antitone hn (Fin.le_def.mpr h)
    · positivity
  · rw [hv i (not_le.mp h)]
    simp

end Problems.LinearAlgebra.courant_fischer
