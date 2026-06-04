import Mathlib
import Problems.Minif2f.numbertheory_xsqpysqintdenomeq.Defs
import Problems.Minif2f.numbertheory_xsqpysqintdenomeq.proofs.L_den_one_eq_int
import Problems.Minif2f.numbertheory_xsqpysqintdenomeq.proofs.L_intcast_sub_den

namespace Problems.Minif2f.numbertheory_xsqpysqintdenomeq

-- Decompose `(a+b).den = 1 ⇒ a.den = b.den` via "a+b is an integer".
-- `den_one_eq_int` extracts the integer witness n with a+b = ↑n;
-- `intcast_sub_den` says (↑n - a).den = a.den (subtracting a rational
-- from an integer preserves the denominator). Combine: b = ↑n - a, so
-- b.den = (↑n - a).den = a.den.
theorem s9352 : ∀ a b : ℚ, (a + b).den = 1 → a.den = b.den  := by
  intro a b h
  obtain ⟨n, hn⟩ := den_one_eq_int (a + b) h
  have h_sub := intcast_sub_den a n
  have hb : b = (↑n : ℚ) - a := by linarith
  rw [hb]
  exact h_sub.symm

end Problems.Minif2f.numbertheory_xsqpysqintdenomeq
