import Mathlib
import Problems.gen_generates.Defs
import Problems.gen_generates.proofs._strategy_s130

namespace Problems.gen_generates

theorem s126_sub_2 : ∀ (n : ℕ) [Fact (2 ≤ n)] (k : ℤ),
    (gen n) ^ k = Multiplicative.ofAdd (k • (1 : ZMod n)) := s130

end Problems.gen_generates
