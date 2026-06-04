import Mathlib
import Problems.Minif2f.imo_1973_p3.Defs
import Problems.Minif2f.imo_1973_p3.proofs.L_bound_via_cauchy_schwarz
import Problems.Minif2f.imo_1973_p3.proofs.L_reduce_to_y_substitution

namespace Problems.Minif2f.imo_1973_p3

-- Decompose via the substitution y = x + 1/x (since x ≠ 0): from existence of a real
-- root x of the quartic, build y with y^2 ≥ 4 and a*y + b = 2 - y^2 (reduce_to_y_substitution);
-- then bound a^2 + b^2 ≥ 4/5 (bound_via_cauchy_schwarz) by Cauchy-Schwarz plus y^2 ≥ 4.
theorem s610 : ∀ (a b : ℝ) (h₀ : ∃ x, x ^ 4 + a * x ^ 3 + b * x ^ 2 + a * x + 1 = 0), 4 / 5 ≤ a ^ 2 + b ^ 2  := by
  intro a b h₀
  have h_red := reduce_to_y_substitution a b h₀
  obtain ⟨y, hy_sq, hy_eq⟩ := h_red
  exact bound_via_cauchy_schwarz a b y hy_sq hy_eq

end Problems.Minif2f.imo_1973_p3
