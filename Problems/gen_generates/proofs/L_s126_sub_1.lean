import Mathlib
import Problems.gen_generates.Defs

namespace Problems.gen_generates

theorem s126_sub_1 : ∀ (n : ℕ) [Fact (2 ≤ n)] (a : ZMod n),
    (((a.val : ℤ) : ZMod n)) = a := by sorry

end Problems.gen_generates
