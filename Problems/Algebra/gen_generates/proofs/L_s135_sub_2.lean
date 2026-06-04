import Mathlib
import Problems.Algebra.gen_generates.Defs

namespace Problems.Algebra.gen_generates

theorem s135_sub_2 : ∀ (n : ℕ) [Fact (2 ≤ n)] (a b : ZMod n),
    ZMod.val a = ZMod.val b → a = b := by
  intro n inst a b h
  cases n with
  | zero => exact absurd inst.out (by omega)
  | succ m => exact Fin.ext h

end Problems.Algebra.gen_generates
