import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- continuous_on_f_three: ContinuousOn.sub of two rpow terms; first is id^const (positive on Ioi 3),
-- second is const^(const^id) built by two nested ContinuousOn.rpow applications.
theorem continuous_on_f_three :
    ContinuousOn
      (fun t : ℝ => t ^ (2 : ℝ) ^ Real.sqrt 2 - Real.sqrt 2 ^ (2 : ℝ) ^ t)
      (Set.Ioi 3) := by
  apply ContinuousOn.sub
  · apply ContinuousOn.rpow continuousOn_id continuousOn_const
    intro x hx
    left; simp only [id]
    have := Set.mem_Ioi.mp hx; linarith
  · apply ContinuousOn.rpow continuousOn_const
    · apply ContinuousOn.rpow continuousOn_const continuousOn_id
      intro x _; left; norm_num
    · intro x _; left; exact Real.sqrt_ne_zero'.mpr (by norm_num)

end Problems.Minif2f.amc12b_2021_p21
