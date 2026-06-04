import Mathlib
import Problems.Algebra.gen_generates.Defs

namespace Problems.Algebra.gen_generates

theorem s127_sub_1 : ∀ (n : ℕ) [Fact (2 ≤ n)] (a : ZMod n),
    (((a.val : ℤ) : ZMod n)) = (a.val : ZMod n) := by norm_num

end Problems.Algebra.gen_generates
