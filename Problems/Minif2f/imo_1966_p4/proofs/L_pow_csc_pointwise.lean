import Mathlib
import Problems.Minif2f.imo_1966_p4.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1966_p4

open Real in
-- pow_csc_pointwise: csc(2^k·x) = cot(2^(k-1)·x) − cot(2^k·x)
-- Nonzero conditions extracted from h₀; tan→sin/cos + sin_two_mul/cos_two_mul,
-- then field_simp+ring close the rational trig identity.
theorem pow_csc_pointwise : ∀ (n : ℕ) (x : ℝ)
    (h₀ : ∀ k : ℕ, 0 < k → ∀ m : ℤ, x ≠ m * π / 2 ^ k) (h₁ : 0 < n)
    (k : ℕ), 0 < k →
    1 / Real.sin (2 ^ k * x) = 1 / Real.tan (2 ^ (k-1) * x) - 1 / Real.tan (2 ^ k * x) := by
  intro n x h₀ _h₁ k hk
  have hpow : (2:ℝ)^k = 2 * (2:ℝ)^(k-1) := by
    have hk1 : k - 1 + 1 = k := Nat.succ_pred_eq_of_pos hk
    nth_rw 1 [← hk1]; ring
  have hpow_ne : (2:ℝ)^k ≠ 0 := by positivity
  have hsin_k : Real.sin ((2:ℝ)^k * x) ≠ 0 := by
    intro heq
    rw [Real.sin_eq_zero_iff] at heq
    obtain ⟨m, hm⟩ := heq
    exact h₀ k hk m (by rw [eq_div_iff hpow_ne]; linear_combination -hm)
  have hsin_k1 : Real.sin ((2:ℝ)^(k-1) * x) ≠ 0 := by
    intro heq
    rw [Real.sin_eq_zero_iff] at heq
    obtain ⟨m, hm⟩ := heq
    exact h₀ k hk (2 * m) (by
      push_cast
      rw [eq_div_iff hpow_ne, hpow]
      linear_combination -2 * hm)
  have hcos_k1 : Real.cos ((2:ℝ)^(k-1) * x) ≠ 0 := by
    intro heq
    rw [Real.cos_eq_zero_iff] at heq
    obtain ⟨m, hm⟩ := heq
    exact h₀ k hk (2 * m + 1) (by
      push_cast
      rw [eq_div_iff hpow_ne, hpow]
      linear_combination 2 * hm)
  rw [Real.tan_eq_sin_div_cos, Real.tan_eq_sin_div_cos]
  rw [show (2:ℝ)^k * x = 2 * ((2:ℝ)^(k-1) * x) by rw [hpow]; ring]
  rw [Real.sin_two_mul, Real.cos_two_mul]
  field_simp [hsin_k1, hcos_k1]
  ring

end Problems.Minif2f.imo_1966_p4
