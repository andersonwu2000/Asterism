import Mathlib
import Problems.gen_generates.Defs

namespace Problems.gen_generates

theorem s129_sub_2 : ∀ (n : ℕ) [Fact (2 ≤ n)] (x y : G n),
    Multiplicative.toAdd x = Multiplicative.toAdd y → x = y := by norm_num

end Problems.gen_generates
