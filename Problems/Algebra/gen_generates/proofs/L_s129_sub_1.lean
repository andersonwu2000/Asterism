import Mathlib
import Problems.Algebra.gen_generates.Defs

namespace Problems.Algebra.gen_generates

theorem s129_sub_1 : ∀ (n : ℕ) [Fact (2 ≤ n)] (a : ZMod n),
    Multiplicative.toAdd (Multiplicative.ofAdd a : G n) = a := by norm_num

end Problems.Algebra.gen_generates
