import Mathlib
import Problems.gen_generates.Defs
import Problems.gen_generates.proofs._strategy_s129

namespace Problems.gen_generates

theorem s126_sub_4 : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n),
    Multiplicative.ofAdd (Multiplicative.toAdd x) = x := s129

end Problems.gen_generates
