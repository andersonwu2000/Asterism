import Mathlib
import Problems.Minif2f.amc12a_2019_p9.Defs
import Problems.Minif2f.amc12a_2019_p9.proofs.L_a_closed_form

namespace Problems.Minif2f.amc12a_2019_p9

-- Reduce to a closed-form expression a n = 3 / (4 n - 1) for n ≥ 1.
-- Combinator: instantiate the closed form at n = 2019; the residual 3 / (4*2019 - 1) = 3 / 8075 is pure arithmetic for norm_num.
theorem s9268 : ∀ (a : ℕ → ℚ) (h₀ : a 1 = 1) (h₁ : a 2 = 3 / 7) (h₂ : ∀ n, a (n + 2) = a n * a (n + 1) / (2 * a n - a (n + 1))), a 2019 = 3 / 8075  := by
  intro a h₀ h₁ h₂
  have h_closed := a_closed_form a h₀ h₁ h₂ 2019 (by norm_num)
  rw [h_closed]
  norm_num

end Problems.Minif2f.amc12a_2019_p9
