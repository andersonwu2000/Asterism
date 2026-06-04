import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs.L_no_such_fun

namespace Problems.Minif2f.imo_1987_p4

-- Contrapositive: ¬(∃ n, f(f n) ≠ n+1987) ⇒ ∀ n, f(f n) = n+1987, contradicting no_such_fun.
-- Sub-goal `no_such_fun` carries the IMO 1987 P4 content (injectivity on ℕ + odd-modulus
-- involution counting on ℤ/1987); this Backward shell only reduces the ∃ to its negation.
theorem s9293 : ∀ (f : ℕ → ℕ), ∃ n, f (f n) ≠ n + 1987 := by
  intro f
  have h_no_such_fun := no_such_fun f
  by_contra hne
  push_neg at hne
  exact h_no_such_fun hne

end Problems.Minif2f.imo_1987_p4
