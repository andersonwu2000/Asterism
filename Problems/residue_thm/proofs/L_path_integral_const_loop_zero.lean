import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem path_integral_const_loop_zero
    (g : ℂ → ℂ) (c : ℂ) :
    (∫ t in (0:ℝ)..1, g ((fun _ : ℝ => c) t) * deriv (fun _ : ℝ => c) t) = 0 := by norm_num

end Problems.residue_thm
