import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs
import Problems.Minif2f.aime_1987_p8.proofs.L_exists_two_k_of_ge_113

namespace Problems.Minif2f.aime_1987_p8

-- Contradict uniqueness for `n ≥ 113` by exhibiting two distinct `k` in the
-- admissible interval. Sub-goal `exists_two_k_of_ge_113` does the arithmetic.
theorem s760 : ∀ n ∈ { n : ℕ | 0 < n ∧ ∃! k : ℕ, (8 : ℝ) / 15 < n / (n + k) ∧ (n : ℝ) / (n + k) < 7 / 13 }, n ≤ 112  := by
  intro n hn
  by_contra h_gt
  have h113 : 113 ≤ n := Nat.lt_of_not_le h_gt
  obtain ⟨_h_pos, _k0, _hk0, hk_unique⟩ := hn
  obtain ⟨k1, k2, hne, hk1, hk2⟩ := exists_two_k_of_ge_113 n h113
  have e1 := hk_unique k1 hk1
  have e2 := hk_unique k2 hk2
  exact hne (e1.trans e2.symm)
end Problems.Minif2f.aime_1987_p8
