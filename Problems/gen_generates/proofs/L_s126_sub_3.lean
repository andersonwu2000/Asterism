import Mathlib
import Problems.gen_generates.Defs
import Problems.gen_generates.proofs._strategy_s128

namespace Problems.gen_generates

theorem s126_sub_3 : ∀ (n : ℕ) [Fact (2 ≤ n)] (k : ℤ),
    k • (1 : ZMod n) = (k : ZMod n) := s128

end Problems.gen_generates
