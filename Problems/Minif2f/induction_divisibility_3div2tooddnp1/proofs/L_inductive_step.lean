import Mathlib
import Problems.Minif2f.induction_divisibility_3div2tooddnp1.Defs

namespace Problems.Minif2f.induction_divisibility_3div2tooddnp1

-- entry_kind: Builder
theorem inductive_step : ∀ (k : ℕ), 3 ∣ 2 ^ (2 * k + 1) + 1 → 3 ∣ 2 ^ (2 * (k + 1) + 1) + 1 := by grind

end Problems.Minif2f.induction_divisibility_3div2tooddnp1
