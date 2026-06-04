import Mathlib
import Problems.Minif2f.mathd_numbertheory_252.Defs

namespace Problems.Minif2f.mathd_numbertheory_252

open Nat

-- Leaf-bypass: `7! % 23 = 3` is a pure numeric computation closed by `decide`.
-- The factorial notation `!` is scoped under `Nat`; `open Nat` is required so
-- the theorem statement parses (does not alter the signature text itself).
theorem s9308 : 7! % 23 = 3  := by decide

end Problems.Minif2f.mathd_numbertheory_252
