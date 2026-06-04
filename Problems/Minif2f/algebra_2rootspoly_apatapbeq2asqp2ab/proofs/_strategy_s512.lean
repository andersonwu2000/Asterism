import Mathlib
import Problems.Minif2f.algebra_2rootspoly_apatapbeq2asqp2ab.Defs

namespace Problems.Minif2f.algebra_2rootspoly_apatapbeq2asqp2ab

-- Pure ring identity over ℂ: expand `(a+a)*(a+b) = 2*a^2 + 2*(a*b)`.
-- No sub-goals; `ring` discharges the goal after introducing `a b`.
theorem s512 : ∀ (a b : ℂ), (a + a) * (a + b) = 2 * a ^ 2 + 2 * (a * b)  := by
  intro a b
  ring

end Problems.Minif2f.algebra_2rootspoly_apatapbeq2asqp2ab
