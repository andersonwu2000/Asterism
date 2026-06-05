import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_norm_sq_eq_sum_repr_sq
import Problems.LinearAlgebra.courant_fischer.proofs.L_rayleigh_numerator_in_eigenbasis
import Problems.LinearAlgebra.courant_fischer.proofs.L_weighted_eigenvalue_sum_le

namespace Problems.LinearAlgebra.courant_fischer

-- Spectral half (W-free): expand Rayleigh in the eigenbasis and bound by λ_k.
-- hnum: ⟪Tx,x⟫ = ∑ᵢ λᵢ·(repr x i)²  (own sub-goal; dedupes to sibling).
-- hnorm: ‖x‖² = ∑ᵢ (repr x i)²  (Parseval, leaf).
-- hsum_le: ∑ᵢ λᵢ·(repr x i)² ≤ λ_k·∑ᵢ (repr x i)²  (low modes vanish + antitone).
-- Combine by clearing the positive denominator ‖x‖²>0.
theorem s11626
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    ∀ x : E, x ≠ 0 →
      (∀ i : Fin n, (i : ℕ) < (k : ℕ) →
        @inner ℝ E _ ((hT.eigenvectorBasis hn) i) x = 0) →
      @inner ℝ E _ (T x) x / ‖x‖ ^ 2 ≤ hT.eigenvalues hn k  := by
  intro x hx hzero
  have hnum : @inner ℝ E _ (T x) x
      = ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    rayleigh_numerator_in_eigenbasis hT hn x
  have hnorm : ‖x‖ ^ 2 = ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    norm_sq_eq_sum_repr_sq hT hn x
  have hsum_le : ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2
      ≤ hT.eigenvalues hn k * ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    weighted_eigenvalue_sum_le hT hn k x hzero
  have hpos : (0:ℝ) < ‖x‖ ^ 2 := pow_pos (norm_pos_iff.mpr hx) 2
  rw [div_le_iff₀ hpos, hnum, hnorm]
  exact hsum_le
end Problems.LinearAlgebra.courant_fischer
