import Mathlib
import Problems.gen_generates.Defs

namespace Problems.gen_generates

theorem s6_s3_main_sub_2_sub_2 : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n) (k : ℤ),
    Multiplicative.ofAdd (Multiplicative.toAdd x) = x := by
  intros
  exact ofAdd_toAdd _

end Problems.gen_generates
