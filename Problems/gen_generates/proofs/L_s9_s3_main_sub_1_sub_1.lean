import Mathlib
import Problems.gen_generates.Defs

namespace Problems.gen_generates

theorem s9_s3_main_sub_1_sub_1 : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n) (k : ℤ),
    k • (1 : ZMod n) = (k : ZMod n) := by
  intros n _inst x k
  exact zsmul_one k

end Problems.gen_generates
