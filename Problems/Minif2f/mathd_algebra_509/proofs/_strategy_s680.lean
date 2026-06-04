import Mathlib
import Problems.Minif2f.mathd_algebra_509.Defs
import Problems.Minif2f.mathd_algebra_509.proofs.L_inner_eq_169_div_36
import Problems.Minif2f.mathd_algebra_509.proofs.L_sqrt_169_div_36_eq

namespace Problems.Minif2f.mathd_algebra_509

-- Reduce √(E) = 13/6 by first simplifying the inner expression E to 169/36
-- (folding √80=4√5, √845=13√5, √45=3√5 and the /√5 division), then evaluating
-- √(169/36) = 13/6.  Both sub-goals are arithmetic / sqrt-eval, simpler than the
-- whole nested-radical equation.
theorem s680 : Real.sqrt ((5 / Real.sqrt 80 + Real.sqrt 845 / 9 + Real.sqrt 45) / Real.sqrt 5) = 13 / 6  := by
  have h_inner := inner_eq_169_div_36
  have h_sqrt := sqrt_169_div_36_eq
  rw [h_inner]; exact h_sqrt

end Problems.Minif2f.mathd_algebra_509
