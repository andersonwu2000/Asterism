import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- derivwithin_phi_eq_zero_at_one: DifferentiableAt.derivWithin + uniqueDiffOn_Icc closes the goal
-- entry_kind: Builder
theorem derivwithin_phi_eq_zero_at_one
    {φ : ℝ → ℝ} (hφ : ContDiff ℝ 1 φ) (hφd1 : deriv φ 1 = 0) :
    derivWithin φ (Set.Icc 0 1) 1 = 0 := by
  have hd : DifferentiableAt ℝ φ 1 := (hφ.differentiable one_ne_zero).differentiableAt
  rw [hd.derivWithin (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1) _
    (Set.right_mem_Icc.mpr (by norm_num : (0:ℝ) ≤ 1)))]
  exact hφd1

end Problems.residue_thm
