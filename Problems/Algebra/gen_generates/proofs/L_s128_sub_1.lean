import Mathlib
import Problems.Algebra.gen_generates.Defs

namespace Problems.Algebra.gen_generates

theorem s128_sub_1 : ∀ (n : ℕ) [Fact (2 ≤ n)] (k : ℤ),
    k • (1 : ZMod n) = (k : ZMod n) * 1 := by norm_num

end Problems.Algebra.gen_generates
