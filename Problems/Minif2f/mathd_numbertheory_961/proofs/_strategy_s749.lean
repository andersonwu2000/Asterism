import Mathlib
import Problems.Minif2f.mathd_numbertheory_961.Defs

namespace Problems.Minif2f.mathd_numbertheory_961

-- Pure decidable arithmetic on `Nat`: 2003 = 182*11 + 1.
-- `decide` reduces the kernel `Nat.mod` computation directly.
theorem s749 : 2003 % 11 = 1  := by decide

end Problems.Minif2f.mathd_numbertheory_961
