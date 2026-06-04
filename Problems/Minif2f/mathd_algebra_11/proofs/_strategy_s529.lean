import Mathlib
import Problems.Minif2f.mathd_algebra_11.Defs

namespace Problems.Minif2f.mathd_algebra_11

-- Direct proof: from h₂ + (a ≠ 2b) derive 4a+3b = 5(a-2b), so a = 13b.
-- Then a ≠ b forces b ≠ 0, and (13b+11b)/(13b-b) = 24b/12b = 2 closes by field_simp + ring.
theorem s529 : ∀ (a b : ℝ) (h₀ : a ≠ b) (h₁ : a ≠ 2 * b) (h₂ : (4 * a + 3 * b) / (a - 2 * b) = 5), (a + 11 * b) / (a - b) = 2  := by
  intro a b h₀ h₁ h₂
  have h2b : a - 2 * b ≠ 0 := sub_ne_zero.mpr h₁
  have hb  : a - b     ≠ 0 := sub_ne_zero.mpr h₀
  have key : 4 * a + 3 * b = 5 * (a - 2 * b) := by
    rw [div_eq_iff h2b] at h₂
    linarith
  have ha : a = 13 * b := by linarith
  have hbne : b ≠ 0 := by
    intro hbz
    apply h₀
    rw [ha, hbz]; ring
  rw [ha]
  field_simp
  ring
end Problems.Minif2f.mathd_algebra_11
