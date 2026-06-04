import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- func2_continuous_on: ContinuousOn.rpow with constant base √2 (≠ 0) and continuous exponent 2^x
theorem func2_continuous_on :
    ContinuousOn (fun x : ℝ => Real.sqrt 2 ^ ((2:ℝ)^x)) (Set.Icc (2:ℝ) 4) := by
  apply ContinuousOn.rpow continuousOn_const
  · apply Continuous.continuousOn
    exact continuous_const.rpow continuous_id' (fun _ => Or.inl (by norm_num))
  · intro x _
    left
    exact Real.sqrt_ne_zero'.mpr (by norm_num)

end Problems.Minif2f.amc12b_2021_p21
