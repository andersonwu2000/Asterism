import Mathlib
import Problems.Minif2f.mathd_numbertheory_37.Defs

namespace Problems.Minif2f.mathd_numbertheory_37

-- Direct kernel computation: `Nat.lcm` is definitionally computable on
-- numeric literals, so `decide` reduces both sides to `90900909` and closes
-- the goal without any sub-goals (leaf-bypass).
theorem s724 : Nat.lcm 9999 100001 = 90900909  := by decide

end Problems.Minif2f.mathd_numbertheory_37
