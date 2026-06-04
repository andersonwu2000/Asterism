import Mathlib
import Problems.Minif2f.imo_2006_p3.Defs
import Problems.Minif2f.imo_2006_p3.proofs.L_factored_form_bound_imo2006
import Problems.Minif2f.imo_2006_p3.proofs.L_factor_cyclic_sum_quartic

namespace Problems.Minif2f.imo_2006_p3

-- Two-piece split: factor the cyclic quartic sum, then bound the factored form.
-- (1) Algebraic identity: LHS = (a-b)(b-c)(a-c)(a+b+c) (pure `ring`).
-- (2) The genuine IMO content: bound on the factored form.
-- Combine via `linarith` on the equality and the bound.
theorem s9297 : ∀ (a b c : ℝ), a * b * (a ^ 2 - b ^ 2) + b * c * (b ^ 2 - c ^ 2) + c * a * (c ^ 2 - a ^ 2) ≤ 9 * Real.sqrt 2 / 32 * (a ^ 2 + b ^ 2 + c ^ 2) ^ 2  := by
  intro a b c
  have h_factor := factor_cyclic_sum_quartic a b c
  have h_bound := factored_form_bound_imo2006 a b c
  linarith [h_factor, h_bound]

end Problems.Minif2f.imo_2006_p3
