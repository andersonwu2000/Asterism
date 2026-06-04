import Mathlib
import Problems.Minif2f.amc12a_2003_p25.Defs
import Problems.Minif2f.amc12a_2003_p25.proofs.L_a_neg_eq_neg_four
import Problems.Minif2f.amc12a_2003_p25.proofs.L_a_pos_contra

namespace Problems.Minif2f.amc12a_2003_p25

-- Trichotomy on a: rule out a > 0; reduce a < 0 to a = -4; a = 0 is the left disjunct.
-- Sub-goals are strictly simpler — each carries an extra sign hypothesis on `a`.
theorem s567 : ∀ (a b : ℝ) (f : ℝ → ℝ) (h₀ : 0 < b) (h₁ : ∀ x, f x = Real.sqrt (a * x ^ 2 + b * x)) (h₂ : { x | 0 ≤ f x } = f '' { x | 0 ≤ f x }), a = 0 ∨ a = -4  := by
  intro a b f h₀ h₁ h₂
  have h_pos : 0 < a → False := a_pos_contra a b f h₀ h₁ h₂
  have h_neg : a < 0 → a = -4 := a_neg_eq_neg_four a b f h₀ h₁ h₂
  rcases lt_trichotomy a 0 with ha | ha | ha
  · exact Or.inr (h_neg ha)
  · exact Or.inl ha
  · exact (h_pos ha).elim

end Problems.Minif2f.amc12a_2003_p25
