import Mathlib
import Problems.gen_generates.Defs

namespace Problems.gen_generates

theorem s9_s3_main_sub_1_sub_2 : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n),
    ∃ k : ℤ, (k : ZMod n) = Multiplicative.toAdd x := by
  intro n _ x
  have hn : 2 ≤ n := Fact.out
  haveI : NeZero n := ⟨by omega⟩
  refine ⟨(Multiplicative.toAdd x).val, ?_⟩
  rw [Int.cast_natCast]
  exact ZMod.natCast_zmod_val _

end Problems.gen_generates
