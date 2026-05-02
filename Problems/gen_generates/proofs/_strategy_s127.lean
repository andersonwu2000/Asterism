import Mathlib
import Problems.gen_generates.Defs
import Problems.gen_generates.proofs.L_s127_sub_1
import Problems.gen_generates.proofs.L_s127_sub_2

namespace Problems.gen_generates

theorem s127 : ∀ (n : ℕ) [Fact (2 ≤ n)] (a : ZMod n),
    (((a.val : ℤ) : ZMod n)) = a := by
  intro n _ a
  have h1 : (((a.val : ℤ) : ZMod n)) = (a.val : ZMod n) := s127_sub_1 n a
  have h2 : (a.val : ZMod n) = a := s127_sub_2 n a
  exact h1.trans h2

end Problems.gen_generates
