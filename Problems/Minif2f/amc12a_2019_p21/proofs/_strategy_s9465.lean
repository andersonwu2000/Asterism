import Mathlib
import Problems.Minif2f.amc12a_2019_p21.Defs
import Problems.Minif2f.amc12a_2019_p21.proofs.L_sum_eq_6z
import Problems.Minif2f.amc12a_2019_p21.proofs.L_sum_inv_eq_6_div_z

namespace Problems.Minif2f.amc12a_2019_p21

-- 2-way decomposition: collapse each Σ_{k=1..12} z^(k^2) using k^2 mod 8 ∈ {1,4,0}
-- with multiplicities (6,3,3) and z^4=-1 ⇒ z^8=1: ∑ z^(k^2) = 6z and ∑ 1/z^(k^2) = 6/z.
-- Closer: (6z)*(6/z) = 36 via field_simp (uses z≠0).
theorem s9465 : ∀ (z : ℂ) (_h₀ : z = (1 + Complex.I) / Real.sqrt 2) (_hz4 : z ^ 4 = -1) (_hzne : z ≠ 0), ((∑ k ∈ Finset.Icc 1 12, z ^ k ^ 2) * (∑ k ∈ Finset.Icc 1 12, 1 / z ^ k ^ 2)) = 36  := by
  intro z h₀ hz4 hzne
  have h_sum1 := sum_eq_6z z h₀ hz4 hzne
  have h_sum2 := sum_inv_eq_6_div_z z h₀ hz4 hzne
  rw [h_sum1, h_sum2]
  field_simp
  norm_num

end Problems.Minif2f.amc12a_2019_p21
