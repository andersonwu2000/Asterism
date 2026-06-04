import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- concave_log_term: scalar multiple of log is concave — restrict strictConcaveOn_log_Ioi to Icc
-- and smul by nonneg constant 2^√2; StrictConcaveOn.concaveOn + ConcaveOn.subset + ConcaveOn.smul
theorem concave_log_term :
    ConcaveOn ℝ (Set.Icc (Real.sqrt 2) 3)
      (fun z => (2:ℝ)^Real.sqrt 2 * Real.log z) := by
  have hlog : ConcaveOn ℝ (Set.Icc (Real.sqrt 2) 3) Real.log := by
    apply ConcaveOn.subset strictConcaveOn_log_Ioi.concaveOn
    · intro x hx
      exact Set.mem_Ioi.mpr (lt_of_lt_of_le (Real.sqrt_pos_of_pos (by norm_num)) hx.1)
    · exact convex_Icc _ _
  have hc : (0 : ℝ) ≤ (2:ℝ)^Real.sqrt 2 := le_of_lt (Real.rpow_pos_of_pos (by norm_num) _)
  have := hlog.smul hc
  simp only [smul_eq_mul] at this
  exact this

end Problems.Minif2f.amc12b_2021_p21
