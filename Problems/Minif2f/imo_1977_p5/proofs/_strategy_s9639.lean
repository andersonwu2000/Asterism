import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs
import Problems.Minif2f.imo_1977_p5.proofs.L_int_box_dispatch_1009
import Problems.Minif2f.imo_1977_p5.proofs.L_sq_bound_1009

namespace Problems.Minif2f.imo_1977_p5

-- Bound |x|,|y| ≤ 31 from x²+y²=1009 (sq_nonneg of the other), then
-- finite-box dispatch via interval_cases. sq_bound_1009 is a generic
-- abstract ℤ-bound lemma; int_box_dispatch_1009 carries bounds as hyps
-- so Builder can drive interval_cases / decide over the small finite box.
theorem s9639 : ∀ (x y : ℤ), x ^ 2 + y ^ 2 = 1009 →
    (abs x = 15 ∧ abs y = 28) ∨ (abs x = 28 ∧ abs y = 15) := by
  intro x y h
  have hx_sq : x ^ 2 ≤ 1009 := by nlinarith [sq_nonneg y]
  have hy_sq : y ^ 2 ≤ 1009 := by nlinarith [sq_nonneg x]
  obtain ⟨hx_lb, hx_ub⟩ := sq_bound_1009 x hx_sq
  obtain ⟨hy_lb, hy_ub⟩ := sq_bound_1009 y hy_sq
  exact int_box_dispatch_1009 x y hx_lb hx_ub hy_lb hy_ub h

end Problems.Minif2f.imo_1977_p5
