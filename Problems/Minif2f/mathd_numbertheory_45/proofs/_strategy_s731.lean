import Mathlib
import Problems.Minif2f.mathd_numbertheory_45.Defs

namespace Problems.Minif2f.mathd_numbertheory_45

-- direct: gcd(6432, 132) = 12, then 12 + 11 = 23 is decidable
theorem s731 : Nat.gcd 6432 132 + 11 = 23  := by decide

end Problems.Minif2f.mathd_numbertheory_45
