import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- Term-wise bound: ∑ λᵢ·(repr x i)² ≤ λ_k·∑ (repr x i)², via `Finset.sum_le_sum`.
-- For i < k the coefficient `repr x i = ⟪eᵢ, x⟫ = 0` (hzero) kills both sides;
-- for k ≤ i, `eigenvalues_antitone` gives λᵢ ≤ λ_k and `(repr x i)² ≥ 0` lifts it.
-- Direct leaf — no sub-goals.
theorem s11634
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) (x : E)
    (hzero : ∀ i : Fin n, (i : ℕ) < (k : ℕ) →
      @inner ℝ E _ ((hT.eigenvectorBasis hn) i) x = 0) :
    ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2
      ≤ hT.eigenvalues hn k * ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2  := by
  rw [Finset.mul_sum]
  apply Finset.sum_le_sum
  intro i _
  rcases lt_or_ge (i : ℕ) (k : ℕ) with hik | hik
  · have hz : (hT.eigenvectorBasis hn).repr x i = 0 := by
      rw [OrthonormalBasis.repr_apply_apply]
      exact hzero i hik
    rw [hz]; simp
  · have hle : hT.eigenvalues hn i ≤ hT.eigenvalues hn k :=
      hT.eigenvalues_antitone hn hik
    exact mul_le_mul_of_nonneg_right hle (sq_nonneg _)

end Problems.LinearAlgebra.courant_fischer
