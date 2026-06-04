import Mathlib
import Problems.Minif2f.amc12a_2010_p22.Defs

namespace Problems.Minif2f.amc12a_2010_p22

-- sum_upper_half_bound: lower bound on upper half sum via |kx-1| ≥ kx-1,
-- using ∑_{k=85}^{119} k = 3570 and |s| = 35 (both by decide after Int cast)
theorem sum_upper_half_bound (x : ℝ) :
    3570 * x - (35:ℝ) ≤ ∑ k ∈ (Finset.Icc (85:ℤ) 119), abs ((k:ℝ) * x - 1) := by
  have h1 : ∑ k ∈ (Finset.Icc (85:ℤ) 119), ((k:ℝ) * x - 1) ≤
            ∑ k ∈ (Finset.Icc (85:ℤ) 119), abs ((k:ℝ) * x - 1) :=
    Finset.sum_le_sum (fun k _ => le_abs_self _)
  have h2 : ∑ k ∈ (Finset.Icc (85:ℤ) 119), ((k:ℝ) * x - 1) = 3570 * x - 35 := by
    have hsum : (∑ k ∈ Finset.Icc (85:ℤ) 119, k : ℤ) = 3570 := by decide
    have hcard : (Finset.Icc (85:ℤ) 119).card = 35 := by decide
    have hcast : (∑ k ∈ Finset.Icc (85:ℤ) 119, (k:ℝ)) = 3570 := by
      have heq : (∑ k ∈ Finset.Icc (85:ℤ) 119, (k:ℝ)) =
          ((∑ k ∈ Finset.Icc (85:ℤ) 119, k : ℤ) : ℝ) := by push_cast; rfl
      rw [heq, hsum]; norm_num
    rw [show ∑ k ∈ (Finset.Icc (85:ℤ) 119), ((k:ℝ) * x - 1) =
      (∑ k ∈ (Finset.Icc (85:ℤ) 119), (k:ℝ)) * x -
      ∑ k ∈ (Finset.Icc (85:ℤ) 119), (1:ℝ) from by
        rw [Finset.sum_sub_distrib, ← Finset.sum_mul]]
    rw [hcast, Finset.sum_const, hcard]
    norm_num
  linarith

end Problems.Minif2f.amc12a_2010_p22
