import Mathlib
import Problems.Algebra.gen_generates.Defs

namespace Problems.Algebra.gen_generates

theorem s128_sub_2 : ∀ (n : ℕ) [Fact (2 ≤ n)] (k : ℤ),
    (k : ZMod n) * 1 = (k : ZMod n) := by norm_num

end Problems.Algebra.gen_generates
