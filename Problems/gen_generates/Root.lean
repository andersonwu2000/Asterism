import Mathlib
import Problems.gen_generates.Defs
import Problems.gen_generates.proofs._strategy_s3

namespace Problems.gen_generates

theorem main : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n), x ∈ Subgroup.zpowers (gen n) := s3_main

end Problems.gen_generates
