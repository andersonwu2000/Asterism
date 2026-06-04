import Mathlib
import Problems.Minif2f.aimeII_2001_p3.Defs

namespace Problems.Minif2f.aimeII_2001_p3

-- entry_kind: Builder
theorem value_x5 (x : ℕ → ℤ) (h₀ : x 1 = 211) (h₂ : x 2 = 375) (h₃ : x 3 = 420) (h₄ : x 4 = 523) (h₆ : ∀ n ≥ 5, x n = x (n - 1) - x (n - 2) + x (n - 3) - x (n - 4)) : x 5 = 267 := by simp_all only [ge_iff_le, Std.le_refl, Nat.add_one_sub_one, Nat.reduceSub, Int.reduceSub, Int.reduceAdd]

end Problems.Minif2f.aimeII_2001_p3
