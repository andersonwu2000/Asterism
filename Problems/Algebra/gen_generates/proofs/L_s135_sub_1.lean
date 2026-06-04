import Mathlib
import Problems.Algebra.gen_generates.Defs

namespace Problems.Algebra.gen_generates

theorem s135_sub_1 : ∀ (n : ℕ) [Fact (2 ≤ n)] (a : ZMod n),
    ZMod.val ((a.val : ZMod n)) = a.val := by
  intro n hn a
  haveI : NeZero n := ⟨by have := hn.out; omega⟩
  have hlt := ZMod.val_lt a
  rw [ZMod.val_natCast]
  exact Nat.mod_eq_of_lt hlt

end Problems.Algebra.gen_generates
