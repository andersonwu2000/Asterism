import Mathlib
import Problems.Minif2f.aime_1994_p4.Defs

namespace Problems.Minif2f.aime_1994_p4

-- sum_at_313_gt_1994: converts Int.floor∘Real.logb to Nat.log via
-- Real.floor_logb_natCast + Int.log_natCast, then closes by kernel decide
-- (axiom-free; maxRecDepth lifted for the 313-element finset traversal)
theorem sum_at_313_gt_1994 :
    (∑ k ∈ Finset.Icc 1 313, Int.floor (Real.logb 2 (k : ℕ))) > 1994 := by
  have hconv : ∀ k : ℕ, Int.floor (Real.logb 2 (k : ℝ)) = (Nat.log 2 k : ℤ) := fun k => by
    have h2 : (2 : ℝ) = ((2 : ℕ) : ℝ) := by norm_num
    rw [h2, Real.floor_logb_natCast (Nat.cast_nonneg k), Int.log_natCast]
  simp_rw [hconv]
  set_option maxRecDepth 2000 in decide

end Problems.Minif2f.aime_1994_p4
