import Mathlib
import Problems.Minif2f.amc12a_2019_p21.Defs
import Problems.Minif2f.amc12a_2019_p21.proofs.L_sum_inv_pow_sq_odd
import Problems.Minif2f.amc12a_2019_p21.proofs.L_sum_inv_pow_sq_two_mod_four
import Problems.Minif2f.amc12a_2019_p21.proofs.L_sum_inv_pow_sq_zero_mod_four

namespace Problems.Minif2f.amc12a_2019_p21

-- 3-way decomposition: partition Finset.Icc 1 12 by k mod 4 residue class.
-- Odd k (1,3,5,7,9,11) → k^2 mod 8 = 1, so 1/z^(k^2) = 1/z (sub-sum 6/z).
-- k ≡ 2 mod 4 (2,6,10) → k^2 mod 8 = 4, so 1/z^(k^2) = 1/(-1) = -1 (sub-sum -3).
-- k ≡ 0 mod 4 (4,8,12) → k^2 mod 8 = 0, so 1/z^(k^2) = 1 (sub-sum 3).
-- Closer: 6/z + (-3) + 3 = 6/z.
theorem s9636 : ∀ (z : ℂ) (_h₀ : z = (1 + Complex.I) / Real.sqrt 2) (_hz4 : z ^ 4 = -1) (_hzne : z ≠ 0), (∑ k ∈ Finset.Icc 1 12, 1 / z ^ k ^ 2) = 6 / z  := by
  intro z h₀ hz4 hzne
  have h_odd := sum_inv_pow_sq_odd z h₀ hz4 hzne
  have h_2mod := sum_inv_pow_sq_two_mod_four z h₀ hz4 hzne
  have h_0mod := sum_inv_pow_sq_zero_mod_four z h₀ hz4 hzne
  have hpart : (Finset.Icc 1 12 : Finset ℕ) =
    ({1,3,5,7,9,11} : Finset ℕ) ∪ ({2,6,10} : Finset ℕ) ∪ ({4,8,12} : Finset ℕ) := by decide
  rw [hpart]
  rw [Finset.sum_union (by decide), Finset.sum_union (by decide)]
  rw [h_odd, h_2mod, h_0mod]
  ring

end Problems.Minif2f.amc12a_2019_p21
