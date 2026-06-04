import Mathlib
import Problems.Algebra.gen_generates.Defs
import Problems.Algebra.gen_generates.proofs.L_s135_sub_1
import Problems.Algebra.gen_generates.proofs.L_s135_sub_2

namespace Problems.Algebra.gen_generates

theorem s135 : ∀ (n : ℕ) [Fact (2 ≤ n)] (a : ZMod n),
    (a.val : ZMod n) = a := by
  intro n _inst a
  have h : ZMod.val ((a.val : ZMod n)) = ZMod.val a := s135_sub_1 n a
  exact s135_sub_2 n (a.val : ZMod n) a h

end Problems.Algebra.gen_generates
