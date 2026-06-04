import Mathlib
import Problems.Minif2f.aime_1994_p4.Defs

namespace Problems.Minif2f.aime_1994_p4

-- Direct: each ⌊logb 2 k⌋ rewrites to Nat.log 2 k via Real.floor_logb_natCast
-- + Int.log_natCast; the resulting finset-sum inequality on ℕ is decidable.
theorem s9458 : ∀ (m : ℕ), 0 < m → m < 312 →
    (∑ k ∈ Finset.Icc 1 311, Int.floor (Real.logb 2 (k : ℕ))) ≤ 1993  := by
  intro m _ _
  have h : ∀ k ∈ Finset.Icc 1 311,
      Int.floor (Real.logb 2 ((k : ℕ) : ℝ)) = (Nat.log 2 k : ℤ) := by
    intro k hk
    have h2 : (2 : ℝ) = ((2 : ℕ) : ℝ) := by norm_num
    rw [h2, Real.floor_logb_natCast (Nat.cast_nonneg k), Int.log_natCast]
  rw [Finset.sum_congr rfl h]
  set_option maxRecDepth 2000 in decide

end Problems.Minif2f.aime_1994_p4
