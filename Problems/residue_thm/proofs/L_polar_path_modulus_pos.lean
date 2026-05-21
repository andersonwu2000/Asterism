import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- polar_path_modulus_pos: the polar interpolation modulus 1-t+t‖w‖ is positive
-- since ‖w‖>0 (w≠0), 0≤t≤1, so the convex combination of 1 and ‖w‖ stays positive.
theorem polar_path_modulus_pos (w : ℂ) (hw : w ≠ 0)
    (t : ℝ) (ht : t ∈ Set.Icc (0 : ℝ) 1) :
    (0:ℝ) < 1 - t + t * ‖w‖ := by
  have h1 : 0 < ‖w‖ := norm_pos_iff.mpr hw
  have h2 : 0 ≤ t := ht.1
  have h3 : t ≤ 1 := ht.2
  nlinarith [mul_nonneg h2 h1.le]

end Problems.residue_thm
