import Mathlib
import Problems.Minif2f.algebra_2complexrootspoly_xsqp49eqxp7itxpn7i.Defs

namespace Problems.Minif2f.algebra_2complexrootspoly_xsqp49eqxp7itxpn7i

-- Direct: (x+7i)(x-7i) = x^2 - (7i)^2 = x^2 + 49 since I^2 = -1.
-- `ring_nf` reduces both sides to a normal form involving I^2; `Complex.I_sq` rewrites I^2 = -1, then `ring` closes.
theorem s502 : ∀ (x : ℂ), x ^ 2 + 49 = (x + 7 * Complex.I) * (x + -7 * Complex.I)  := by
  intro x
  ring_nf
  rw [Complex.I_sq]
  ring

end Problems.Minif2f.algebra_2complexrootspoly_xsqp49eqxp7itxpn7i
