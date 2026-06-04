import Mathlib
import Problems.Minif2f.amc12a_2019_p21.Defs
import Problems.Minif2f.amc12a_2019_p21.proofs.L_sum_prod_eq_36
import Problems.Minif2f.amc12a_2019_p21.proofs.L_z_ne_zero
import Problems.Minif2f.amc12a_2019_p21.proofs.L_z_pow_four_eq_neg_one

namespace Problems.Minif2f.amc12a_2019_p21

-- 3-way decomposition: extract `z^4 = -1`, extract `z ≠ 0`, then prove product=36 given those two
-- abstract hypotheses. Math: k^2 mod 8 over k=1..12 gives 6×1 + 3×4 + 3×0, so the two sums each
-- collapse to 6z resp. 6/z (using z^4 = -1 ⇒ z^8 = 1), product = 36.
theorem s9364 : ∀ (z : ℂ) (h₀ : z = (1 + Complex.I) / Real.sqrt 2), ((∑ k ∈ Finset.Icc 1 12, z ^ k ^ 2) * (∑ k ∈ Finset.Icc 1 12, 1 / z ^ k ^ 2)) = 36  := by
  intro z h₀
  have h_z4 : z ^ 4 = -1 := z_pow_four_eq_neg_one z h₀
  have h_zne : z ≠ 0 := z_ne_zero z h₀
  exact sum_prod_eq_36 z h₀ h_z4 h_zne

end Problems.Minif2f.amc12a_2019_p21
