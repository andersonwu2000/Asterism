import Mathlib
import Problems.Minif2f.mathd_numbertheory_102.Defs

namespace Problems.Minif2f.mathd_numbertheory_102

-- Direct kernel evaluation: 2^8 = 256 and 256 % 5 = 1.
-- `decide` reduces the closed `Nat` expression via the `DecidableEq Nat` instance,
-- so no sub-goals are required — this is a leaf.
theorem s518 : 2 ^ 8 % 5 = 1  := by decide

end Problems.Minif2f.mathd_numbertheory_102
