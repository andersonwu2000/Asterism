import Mathlib
import Problems.Minif2f.mathd_numbertheory_101.Defs

namespace Problems.Minif2f.mathd_numbertheory_101

-- Pure ℕ decidable arithmetic: 17 * 18 = 306 = 76 * 4 + 2, so 306 % 4 = 2.
-- `decide` reduces `17 * 18 % 4 = 2` to `Nat.beq` and discharges by reflection.
theorem s517 : 17 * 18 % 4 = 2  := by decide

end Problems.Minif2f.mathd_numbertheory_101
