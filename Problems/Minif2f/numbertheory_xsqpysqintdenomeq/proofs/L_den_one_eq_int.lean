import Mathlib
import Problems.Minif2f.numbertheory_xsqpysqintdenomeq.Defs

namespace Problems.Minif2f.numbertheory_xsqpysqintdenomeq

-- den_one_eq_int: Rat.num_div_den + hq rewrites ↑q.num / ↑q.den = q to ↑q.num = q
theorem den_one_eq_int : ∀ q : ℚ, q.den = 1 → ∃ n : ℤ, q = (↑n : ℚ) := by
  intro q hq
  use q.num
  have h := Rat.num_div_den q
  rw [hq, Nat.cast_one, div_one] at h
  exact h.symm

end Problems.Minif2f.numbertheory_xsqpysqintdenomeq
