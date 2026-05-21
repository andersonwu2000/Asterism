import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- segment_contdiff: linear path t ↦ z + t·h is C¹ on [0,1] via smul_const
theorem segment_contdiff (z h : ℂ) :
    ContDiffOn ℝ 1 (fun t : ℝ => z + (t:ℂ) * h) (Set.Icc 0 1) := by
  apply ContDiff.contDiffOn
  apply ContDiff.add contDiff_const
  have heq : (fun t : ℝ => (t : ℂ) * h) = fun t : ℝ => t • h := by
    ext t; simp [Algebra.smul_def]
  rw [heq]
  exact contDiff_id.smul_const h

end Problems.residue_thm
