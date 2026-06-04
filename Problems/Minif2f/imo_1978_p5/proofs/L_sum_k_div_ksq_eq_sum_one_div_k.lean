import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs

namespace Problems.Minif2f.imo_1978_p5

-- sum_k_div_ksq_eq_sum_one_div_k: k/k² = 1/k pointwise via field_simp on k ≥ 1
theorem sum_k_div_ksq_eq_sum_one_div_k :
    ∀ (n : ℕ) (a : ℕ → ℕ), 0 < n →
    (∀ m, m ≤ n → (∑ k ∈ Finset.Icc 1 m, (k : ℝ)) ≤ ∑ k ∈ Finset.Icc 1 m, (a k : ℝ)) →
    (∑ k ∈ Finset.Icc 1 n, (k : ℝ) / (k : ℝ)^2) = ∑ k ∈ Finset.Icc 1 n, (1 : ℝ) / k := by
  intro n a _hn _ha
  apply Finset.sum_congr rfl
  intro k hk
  have hk1 : 1 ≤ k := (Finset.mem_Icc.mp hk).1
  have hk_pos : (0 : ℝ) < k := by exact_mod_cast Nat.lt_of_succ_le hk1
  field_simp

end Problems.Minif2f.imo_1978_p5
