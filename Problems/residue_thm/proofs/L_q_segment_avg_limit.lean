import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem q_segment_avg_limit
    (Q : ℂ → ℂ) (z : ℂ) (h_cont : ContinuousAt Q z) :
    Filter.Tendsto (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h))
      (nhds 0) (nhds (Q z)) := by sorry

end Problems.residue_thm
