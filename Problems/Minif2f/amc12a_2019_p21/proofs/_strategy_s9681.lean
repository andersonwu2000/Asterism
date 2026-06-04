import Mathlib
import Problems.Minif2f.amc12a_2019_p21.Defs
import Problems.Minif2f.amc12a_2019_p21.proofs.L_sum_pow_sq_odd
import Problems.Minif2f.amc12a_2019_p21.proofs.L_sum_pow_sq_two_mod_four
import Problems.Minif2f.amc12a_2019_p21.proofs.L_sum_pow_sq_zero_mod_four

namespace Problems.Minif2f.amc12a_2019_p21

-- 3-way: partition Finset.Icc 1 12 by k mod 4 residue class.
-- Odd k (1,3,5,7,9,11) → k^2 ≡ 1 (mod 8), z^(k^2) = z, sub-sum = 6z.
-- k ≡ 2 mod 4 (2,6,10) → k^2 ≡ 4 (mod 8), z^(k^2) = z^4 = -1, sub-sum = -3.
-- k ≡ 0 mod 4 (4,8,12) → k^2 ≡ 0 (mod 8), z^(k^2) = 1, sub-sum = 3.
-- Closer: rewrite the Icc as the disjoint union; sub-sums combine via ring (6z + (-3) + 3 = 6z).
theorem s9681 : ∀ (z : ℂ) (_h₀ : z = (1 + Complex.I) / Real.sqrt 2)
    (_hz4 : z ^ 4 = -1) (_hzne : z ≠ 0) (_hz8 : z ^ 8 = 1),
    (∑ k ∈ Finset.Icc 1 12, z ^ k ^ 2) = 6 * z  := by
  intro z h₀ hz4 hzne hz8
  have h_odd := sum_pow_sq_odd z h₀ hz4 hzne hz8
  have h_2mod := sum_pow_sq_two_mod_four z h₀ hz4 hzne hz8
  have h_0mod := sum_pow_sq_zero_mod_four z h₀ hz4 hzne hz8
  have hpart : (Finset.Icc 1 12 : Finset ℕ) =
    ({1,3,5,7,9,11} : Finset ℕ) ∪ ({2,6,10} : Finset ℕ) ∪ ({4,8,12} : Finset ℕ) := by decide
  rw [hpart]
  rw [Finset.sum_union (by decide), Finset.sum_union (by decide)]
  rw [h_odd, h_2mod, h_0mod]
  ring

end Problems.Minif2f.amc12a_2019_p21
