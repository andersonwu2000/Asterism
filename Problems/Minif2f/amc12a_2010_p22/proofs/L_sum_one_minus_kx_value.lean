import Mathlib
import Problems.Minif2f.amc12a_2010_p22.Defs

namespace Problems.Minif2f.amc12a_2010_p22

-- sum_one_minus_kx_value: Finset.sum_const + decide (maxRecDepth 2000) + push_cast/rfl for
-- the ℤ-indexed Icc sum; evaluates ∑ k∈Icc 1 84, (1 - k*x) = 84 - 3570*x by
-- splitting via sum_sub_distrib, computing card=84 and ∑k=3570 at ℤ, then casting.
set_option maxRecDepth 2000 in
theorem sum_one_minus_kx_value (x : ℝ) :
    ∑ k ∈ (Finset.Icc (1:ℤ) 84), (1 - (k:ℝ) * x) = 84 - 3570 * x := by
  have hcard : (Finset.Icc (1:ℤ) 84).card = 84 := by decide
  have hsum : (∑ k ∈ Finset.Icc (1:ℤ) 84, k : ℤ) = 3570 := by decide
  have hk : ∑ k ∈ (Finset.Icc (1:ℤ) 84), (k : ℝ) = 3570 := by
    have heq : ∑ k ∈ (Finset.Icc (1:ℤ) 84), (k : ℝ) =
        ↑(∑ k ∈ Finset.Icc (1:ℤ) 84, k : ℤ) := by push_cast; rfl
    rw [heq, hsum]; norm_num
  simp only [Finset.sum_sub_distrib, ← Finset.sum_mul]
  rw [Finset.sum_const, hcard, hk]
  norm_num

end Problems.Minif2f.amc12a_2010_p22
