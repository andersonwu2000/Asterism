import Mathlib
import Problems.gen_generates.Defs

namespace Problems.gen_generates

theorem s127_sub_1 : ∀ (n : ℕ) [Fact (2 ≤ n)] (a : ZMod n),
    (((a.val : ℤ) : ZMod n)) = (a.val : ZMod n) := by norm_num

end Problems.gen_generates
