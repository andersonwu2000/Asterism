import Mathlib
import Problems.Algebra.gen_generates.Defs

namespace Problems.Algebra.gen_generates

theorem s130_sub_2 : ∀ (n : ℕ) [Fact (2 ≤ n)] (k : ℤ) (x : Multiplicative (ZMod n)),
    x = Multiplicative.ofAdd (Multiplicative.toAdd x) := by norm_num

end Problems.Algebra.gen_generates
