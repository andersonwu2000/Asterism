import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs
import Problems.Minif2f.imo_1974_p5.proofs.L_imo_1974_p5_lower_bound
import Problems.Minif2f.imo_1974_p5.proofs.L_imo_1974_p5_upper_bound

namespace Problems.Minif2f.imo_1974_p5

-- Split `1 < s ∧ s < 2` into the two bound directions, combined by `⟨_, _⟩`.
-- Each direction is the classical IMO 1974 P5 estimate (drop/add a variable in each
-- denominator), structurally independent and roughly equal cost — Backward each.
theorem s9290 : ∀ (a b c d s : ℝ) (h₀ : 0 < a ∧ 0 < b ∧ 0 < c ∧ 0 < d) (h₁ : s = a / (a + b + d) + b / (a + b + c) + c / (b + c + d) + d / (a + c + d)), 1 < s ∧ s < 2  := by
  intro a b c d s h₀ h₁
  have h_lower := imo_1974_p5_lower_bound a b c d s h₀ h₁
  have h_upper := imo_1974_p5_upper_bound a b c d s h₀ h₁

  exact ⟨h_lower, h_upper⟩


end Problems.Minif2f.imo_1974_p5
