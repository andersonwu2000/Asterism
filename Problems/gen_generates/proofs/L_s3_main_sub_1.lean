import Mathlib
import Problems.gen_generates.Defs
import Problems.gen_generates.proofs._strategy_s9

namespace Problems.gen_generates

theorem s3_main_sub_1 : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n),
    ∃ k : ℤ, k • (1 : ZMod n) = Multiplicative.toAdd x := s9_s3_main_sub_1

end Problems.gen_generates
