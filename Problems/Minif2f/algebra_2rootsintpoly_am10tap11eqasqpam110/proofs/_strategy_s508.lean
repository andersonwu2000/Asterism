import Mathlib
import Problems.Minif2f.algebra_2rootsintpoly_am10tap11eqasqpam110.Defs

namespace Problems.Minif2f.algebra_2rootsintpoly_am10tap11eqasqpam110

-- Pure polynomial identity over ℂ: expand (a-10)(a+11) = a^2 + a - 110.
-- Closed directly by `ring`; no sub-goals needed (leaf-bypass).
theorem s508 : ∀ (a : ℂ), (a - 10) * (a + 11) = a ^ 2 + a - 110  := by
  intro a
  ring

end Problems.Minif2f.algebra_2rootsintpoly_am10tap11eqasqpam110
