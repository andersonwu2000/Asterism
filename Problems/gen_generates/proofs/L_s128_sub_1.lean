import Mathlib
import Problems.gen_generates.Defs

namespace Problems.gen_generates

theorem s128_sub_1 : ∀ (n : ℕ) [Fact (2 ≤ n)] (k : ℤ),
    k • (1 : ZMod n) = (k : ZMod n) * 1 := by norm_num

end Problems.gen_generates
