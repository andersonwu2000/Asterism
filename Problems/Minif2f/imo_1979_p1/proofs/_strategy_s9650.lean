import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs

namespace Problems.Minif2f.imo_1979_p1

-- Direct proof: split Icc 1 1319 = Icc 1 659 ⊔ Icc 660 1319 via Ico-consecutive.
-- Convert each Icc to Ico (Icc a b = Ico a (b+1)) so Finset.sum_Ico_consecutive applies,
-- giving sum_low + sum_high = sum_all; rearrange with linarith. Leaf — no sub-goals.
theorem s9650 :
    (∑ k ∈ Finset.Icc (660 : ℕ) 1319, ((1 : ℝ) / (k : ℝ))) =
      (∑ k ∈ Finset.Icc (1 : ℕ) 1319, ((1 : ℝ) / (k : ℝ))) -
        (∑ j ∈ Finset.Icc (1 : ℕ) 659, ((1 : ℝ) / (j : ℝ)))  := by
  rw [show (Finset.Icc 1 1319 : Finset ℕ) = Finset.Ico 1 1320 from by
        ext; simp [Finset.mem_Icc, Finset.mem_Ico]; omega,
      show (Finset.Icc 1 659 : Finset ℕ) = Finset.Ico 1 660 from by
        ext; simp [Finset.mem_Icc, Finset.mem_Ico]; omega,
      show (Finset.Icc 660 1319 : Finset ℕ) = Finset.Ico 660 1320 from by
        ext; simp [Finset.mem_Icc, Finset.mem_Ico]; omega]
  have h := Finset.sum_Ico_consecutive (fun k : ℕ => ((1 : ℝ) / (k : ℝ)))
    (m := 1) (n := 660) (k := 1320) (by norm_num) (by norm_num)
  linarith [h]

end Problems.Minif2f.imo_1979_p1
