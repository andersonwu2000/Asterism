import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- convex_exp_term: ConvexOn for a non-negative scalar multiple of 2^z.
-- Strategy: rewrite 2^z = exp(z * log 2) via rpow_def_of_pos, use convexOn_exp composed
-- with a linear map, then apply ConvexOn.smul with log(√2) ≥ 0.
theorem convex_exp_term :
    ConvexOn ℝ (Set.Icc (Real.sqrt 2) 3)
      (fun z => (2:ℝ)^z * Real.log (Real.sqrt 2)) := by
  have h_log_nonneg : 0 ≤ Real.log (Real.sqrt 2) := by
    apply Real.log_nonneg
    exact Real.one_le_sqrt.mpr (by norm_num)
  have h_conv_2pow : ConvexOn ℝ (Set.Icc (Real.sqrt 2) 3) (fun z => (2:ℝ)^z) := by
    have key : ConvexOn ℝ (Set.Icc (Real.sqrt 2) 3) (fun z => Real.exp (z * Real.log 2)) := by
      apply ConvexOn.subset (convexOn_exp.comp_linearMap (LinearMap.mulRight ℝ (Real.log 2)))
      · intro x hx; simp
      · exact convex_Icc _ _
    convert key using 1
    ext z
    simp [Real.rpow_def_of_pos (by norm_num : (0:ℝ) < 2), mul_comm]
  have h_smul := h_conv_2pow.smul h_log_nonneg
  simp only [smul_eq_mul, mul_comm] at h_smul
  exact h_smul

end Problems.Minif2f.amc12b_2021_p21
