import Mathlib
import Problems.gen_generates.Defs
import Problems.gen_generates.proofs._strategy_s6

namespace Problems.gen_generates

theorem s3_main_sub_2 : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n) (k : ℤ),
    k • (1 : ZMod n) = Multiplicative.toAdd x → (gen n) ^ k = x := s6_s3_main_sub_2

end Problems.gen_generates
