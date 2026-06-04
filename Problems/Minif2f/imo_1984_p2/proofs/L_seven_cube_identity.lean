import Mathlib
import Problems.Minif2f.imo_1984_p2.Defs

namespace Problems.Minif2f.imo_1984_p2

-- entry_kind: Builder
theorem seven_cube_identity : ∀ (x y : ℤ),
    (x + y) ^ 7 - x ^ 7 - y ^ 7
      = 7 * x * y * (x + y) * (x ^ 2 + x * y + y ^ 2) ^ 2 := by grind

end Problems.Minif2f.imo_1984_p2
