import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs.L_cos_gt_on_upper_arc_2

namespace Problems.Minif2f.imo_1965_p1

open Real

-- By contradiction on `x ≤ 7π/4`: assume `7π/4 < x`, combine with `x ≤ 2π`,
-- apply the "cos is > √2/2 on the upper arc" sub-goal, and close via `linarith`
-- against the parent hypothesis `cos x ≤ √2/2`.
-- The cos-on-upper-arc sub-goal is stated with explicit `Real.pi` so that the
-- leaf file (where `π` would otherwise be auto-bound as a free `ℝ`) cannot be
-- killed by the `π := 1, x := 1.8` counterexample that sank prior strategy s9654.
theorem s9702 : ∀ (x : ℝ), 0 ≤ x → x ≤ 2 * π → Real.cos x ≤ Real.sqrt 2 / 2 → x ≤ 7 * π / 4  := by
  intro x h0 h1 hcos
  by_contra hx
  have hx' : 7 * Real.pi / 4 < x := not_le.mp hx
  have h_cos_gt_on_upper_arc := cos_gt_on_upper_arc_2
  have hgt : Real.sqrt 2 / 2 < Real.cos x := h_cos_gt_on_upper_arc x hx' h1
  linarith

end Problems.Minif2f.imo_1965_p1
