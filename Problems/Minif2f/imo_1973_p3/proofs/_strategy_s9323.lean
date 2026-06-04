import Mathlib
import Problems.Minif2f.imo_1973_p3.Defs
import Problems.Minif2f.imo_1973_p3.proofs.L_quartic_to_y_eqn
import Problems.Minif2f.imo_1973_p3.proofs.L_x_ne_zero_of_quartic
import Problems.Minif2f.imo_1973_p3.proofs.L_y_sq_ge_four

namespace Problems.Minif2f.imo_1973_p3

-- Substitution y = x + 1/x: from a real root x of the quartic, build y.
-- (1) x ≠ 0 (else equation reads 1 = 0); (2) (x+1/x)^2 ≥ 4 (AM-GM on x^2, 1/x^2);
-- (3) divide quartic by x^2: a*(x+1/x) + b = 2 - (x+1/x)^2. Combine via ⟨x+1/x, _, _⟩.
theorem s9323 :
  ∀ (a b : ℝ), (∃ x : ℝ, x ^ 4 + a * x ^ 3 + b * x ^ 2 + a * x + 1 = 0) →
  ∃ y : ℝ, 4 ≤ y ^ 2 ∧ a * y + b = 2 - y ^ 2  := by
  intro a b h
  obtain ⟨x, hx⟩ := h
  have h_xne : x ≠ 0 := x_ne_zero_of_quartic a b x hx
  have h_ysq : 4 ≤ (x + 1/x) ^ 2 := y_sq_ge_four x h_xne
  have h_eqn : a * (x + 1/x) + b = 2 - (x + 1/x) ^ 2 :=
    quartic_to_y_eqn a b x h_xne hx
  exact ⟨x + 1/x, h_ysq, h_eqn⟩

end Problems.Minif2f.imo_1973_p3
