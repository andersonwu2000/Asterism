import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs
import Problems.Minif2f.imo_1974_p5.proofs.L_lower_bound_raw

namespace Problems.Minif2f.imo_1974_p5

-- Reduce to the raw inequality (no `s` indirection): rewrite `s` via `h₁` and
-- apply the sub-goal `lower_bound_raw`, which is the classical IMO 1974 P5
-- lower bound on the explicit fraction sum.
theorem s9430 : ∀ (a b c d s : ℝ) (h₀ : 0 < a ∧ 0 < b ∧ 0 < c ∧ 0 < d) (h₁ : s = a / (a + b + d) + b / (a + b + c) + c / (b + c + d) + d / (a + c + d)), 1 < s  := by
  intro a b c d s h₀ h₁
  obtain ⟨ha, hb, hc, hd⟩ := h₀
  rw [h₁]
  exact lower_bound_raw a b c d ha hb hc hd

end Problems.Minif2f.imo_1974_p5
