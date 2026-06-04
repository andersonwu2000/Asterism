import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs
import Problems.Minif2f.imo_1974_p5.proofs.L_frac_a_upper
import Problems.Minif2f.imo_1974_p5.proofs.L_frac_b_upper
import Problems.Minif2f.imo_1974_p5.proofs.L_frac_c_upper
import Problems.Minif2f.imo_1974_p5.proofs.L_frac_d_upper

namespace Problems.Minif2f.imo_1974_p5

-- Split `s < 2` into 4 mediant inequalities (one per fraction in `s`).
-- Each is `x/(denom) < (x+y)/(a+b+c+d)`; summing the 4 strict inequalities
-- gives `s < 2(a+c)/(a+b+c+d) + 2(b+d)/(a+b+c+d) = 2`.
theorem s9491 : ∀ (a b c d s : ℝ) (h₀ : 0 < a ∧ 0 < b ∧ 0 < c ∧ 0 < d) (h₁ : s = a / (a + b + d) + b / (a + b + c) + c / (b + c + d) + d / (a + c + d)), s < 2  := by
  intro a b c d s h₀ h₁
  have h_frac_a := frac_a_upper a b c d s h₀ h₁
  have h_frac_b := frac_b_upper a b c d s h₀ h₁
  have h_frac_c := frac_c_upper a b c d s h₀ h₁
  have h_frac_d := frac_d_upper a b c d s h₀ h₁
  obtain ⟨ha, hb, hc, hd⟩ := h₀
  have habcd : 0 < a + b + c + d := by linarith
  have hsum : (a + c) / (a + b + c + d) + (b + d) / (a + b + c + d) + (a + c) / (a + b + c + d) + (b + d) / (a + b + c + d) = 2 := by
    field_simp
    ring
  rw [h₁]
  linarith

end Problems.Minif2f.imo_1974_p5
