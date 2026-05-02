import Mathlib
import Problems.gen_generates.Defs
import Problems.gen_generates.proofs.L_s128_sub_1
import Problems.gen_generates.proofs.L_s128_sub_2

namespace Problems.gen_generates

theorem s128 : ∀ (n : ℕ) [Fact (2 ≤ n)] (k : ℤ),
    k • (1 : ZMod n) = (k : ZMod n) := by
  intro n _inst k
  have h1 : k • (1 : ZMod n) = (k : ZMod n) * 1 := s128_sub_1 n k
  have h2 : (k : ZMod n) * 1 = (k : ZMod n) := s128_sub_2 n k
  exact h1.trans h2

end Problems.gen_generates
