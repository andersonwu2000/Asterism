import Mathlib
import Problems.Minif2f.amc12a_2019_p9.Defs

namespace Problems.Minif2f.amc12a_2019_p9

-- entry_kind: Builder
theorem induction_step : ∀ (a : ℕ → ℚ) (h₀ : a 1 = 1) (h₁ : a 2 = 3 / 7)
    (h₂ : ∀ n, a (n + 2) = a n * a (n + 1) / (2 * a n - a (n + 1))) (k : ℕ),
    a (k+1) = 3 / (4 * ((k+1:ℕ):ℚ) - 1) →
    a (k+2) = 3 / (4 * ((k+2:ℕ):ℚ) - 1) →
    a (k+3) = 3 / (4 * ((k+3:ℕ):ℚ) - 1) := by
  intro a h₀ h₁ h₂ k hk1 hk2
  have h3 := h₂ (k + 1)
  simp only [show k + 1 + 2 = k + 3 from by omega,
             show k + 1 + 1 = k + 2 from by omega] at h3
  rw [hk1, hk2] at h3
  rw [h3]
  have hd1 : (4 : ℚ) * ↑(k + 1) - 1 ≠ 0 := by push_cast; linarith [Nat.zero_le k]
  have hd2 : (4 : ℚ) * ↑(k + 2) - 1 ≠ 0 := by push_cast; linarith [Nat.zero_le k]
  have hd3 : (4 : ℚ) * ↑(k + 3) - 1 ≠ 0 := by push_cast; linarith [Nat.zero_le k]
  field_simp [hd1, hd2, hd3]
  have hd4 : ((4 : ℚ) * ↑(k + 2) - 1) * 2 - ((4 : ℚ) * ↑(k + 1) - 1) ≠ 0 := by
    push_cast; linarith [Nat.zero_le k]
  rw [div_eq_iff hd4]
  push_cast; ring

end Problems.Minif2f.amc12a_2019_p9
