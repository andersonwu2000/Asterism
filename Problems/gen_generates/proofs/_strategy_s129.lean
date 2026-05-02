import Mathlib
import Problems.gen_generates.Defs
import Problems.gen_generates.proofs.L_s129_sub_1
import Problems.gen_generates.proofs.L_s129_sub_2

namespace Problems.gen_generates

theorem s129 : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n),
    Multiplicative.ofAdd (Multiplicative.toAdd x) = x := by
  intro n _inst x
  apply s129_sub_2 n
  exact s129_sub_1 n (Multiplicative.toAdd x)

end Problems.gen_generates
