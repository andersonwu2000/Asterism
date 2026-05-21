import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem integral_segment_zero
    (Q : ℂ → ℂ) (z : ℂ) :
    (∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * 0)) = Q z := by norm_num

end Problems.residue_thm
