import Mathlib
import Problems.gen_generates.Defs

namespace Problems.gen_generates

theorem s127_sub_2 : ∀ (n : ℕ) [Fact (2 ≤ n)] (a : ZMod n),
    (a.val : ZMod n) = a := by sorry

end Problems.gen_generates
