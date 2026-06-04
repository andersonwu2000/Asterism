import Mathlib
import Problems.Minif2f.amc12a_2010_p22.Defs

namespace Problems.Minif2f.amc12a_2010_p22

-- sum_split_at_84: split Finset.Icc 1 119 sum into Icc 1 84 and Icc 85 119 via disjoint union
theorem sum_split_at_84 (x : ℝ) :
    ∑ k ∈ (Finset.Icc (1:ℤ) (119:ℤ)), abs ((k:ℝ) * x - 1)
      = (∑ k ∈ (Finset.Icc (1:ℤ) 84), abs ((k:ℝ) * x - 1))
        + (∑ k ∈ (Finset.Icc (85:ℤ) 119), abs ((k:ℝ) * x - 1)) := by
  have hd : Disjoint (Finset.Icc (1:ℤ) 84) (Finset.Icc 85 119) := by
    rw [Finset.disjoint_left]
    intro k hk1 hk2
    simp only [Finset.mem_Icc] at hk1 hk2
    omega
  have hu : Finset.Icc (1:ℤ) 84 ∪ Finset.Icc 85 119 = Finset.Icc 1 119 := by
    ext k
    simp only [Finset.mem_union, Finset.mem_Icc]
    omega
  rw [← hu, Finset.sum_union hd]

end Problems.Minif2f.amc12a_2010_p22
