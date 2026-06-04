import Mathlib
import Problems.Minif2f.amc12a_2019_p21.Defs
import Problems.Minif2f.amc12a_2019_p21.proofs.L_sum_eq_6z_using_z8
import Problems.Minif2f.amc12a_2019_p21.proofs.L_z_pow_eight_eq_one

namespace Problems.Minif2f.amc12a_2019_p21

-- 2-way: extract z^8 = 1 (from z^4 = -1), then sum collapses via period-8 partition of k^2 mod 8
-- over k=1..12 (multiplicities 6,3,3 for residues 1,4,0 ⇒ 6z + 3·(-1) + 3·1 = 6z).
theorem s9635 : ∀ (z : ℂ) (_h₀ : z = (1 + Complex.I) / Real.sqrt 2) (_hz4 : z ^ 4 = -1)
    (_hzne : z ≠ 0), (∑ k ∈ Finset.Icc 1 12, z ^ k ^ 2) = 6 * z  := by
  intro z h₀ hz4 hzne
  have h_z8 := z_pow_eight_eq_one z h₀ hz4 hzne
  exact sum_eq_6z_using_z8 z h₀ hz4 hzne h_z8

end Problems.Minif2f.amc12a_2019_p21
