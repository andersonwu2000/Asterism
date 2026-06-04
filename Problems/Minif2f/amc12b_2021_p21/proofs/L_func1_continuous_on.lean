import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- func1_continuous_on: x ↦ x^(2^√2) is continuous on [2,4] via ContinuousOn.rpow with positive base
theorem func1_continuous_on :
    ContinuousOn (fun x : ℝ => x^((2:ℝ)^Real.sqrt 2)) (Set.Icc (2:ℝ) 4) := by
  apply ContinuousOn.rpow continuousOn_id continuousOn_const
  intro x hx
  left
  simp only [id]
  linarith [hx.1]

end Problems.Minif2f.amc12b_2021_p21
