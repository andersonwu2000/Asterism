import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs.L_alt_sum_paired
import Problems.Minif2f.imo_1979_p1.proofs.L_pair_sum_repr

namespace Problems.Minif2f.imo_1979_p1

-- Decompose into: (A) the IMO pairing trick, rewriting the alternating sum
-- as 1979 times a "pair sum" ∑ 1/((660+j)*(1319-j)); and (B) the generic
-- existence of a (numerator, denominator) representation for that pair sum
-- where the denominator is coprime to 1979 (its factors are all < 1979).
theorem s9325 :
    ∃ (a b : ℕ), 0 < b ∧ Nat.Coprime b 1979 ∧ 1979 ∣ a ∧
      (∑ k ∈ Finset.Icc (1 : ℕ) 1319, (-1) ^ (k + 1) * ((1 : ℝ) / k)) = (a : ℝ) / (b : ℝ)  := by
  have hA := alt_sum_paired
  have hB := pair_sum_repr
  obtain ⟨n, d, hd_pos, hd_cop, hsum⟩ := hB
  refine ⟨1979 * n, d, hd_pos, hd_cop, dvd_mul_right 1979 n, ?_⟩
  rw [hA, hsum]
  push_cast
  ring

end Problems.Minif2f.imo_1979_p1
