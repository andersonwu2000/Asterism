import Mathlib
import Problems.gen_generates.Defs

namespace Problems.gen_generates

theorem s6_s3_main_sub_2_sub_1 : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n) (k : ℤ),
    (gen n) ^ k = Multiplicative.ofAdd (k • (1 : ZMod n)) := by
  intro n _ x k
  simp [gen, ← ofAdd_zsmul]

end Problems.gen_generates
