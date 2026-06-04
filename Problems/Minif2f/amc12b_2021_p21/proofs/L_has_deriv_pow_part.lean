import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- has_deriv_pow_part: Real.hasDerivAt_rpow_const gives HasDerivAt for s ↦ s^c at t > 0
theorem has_deriv_pow_part :
    ∀ t : ℝ, 3 < t →
      HasDerivAt (fun s : ℝ => s ^ (2 : ℝ) ^ Real.sqrt 2)
        ((2 : ℝ) ^ Real.sqrt 2 * t ^ ((2 : ℝ) ^ Real.sqrt 2 - 1)) t := by
  intro t ht
  have ht_pos : (0 : ℝ) < t := by linarith
  have := Real.hasDerivAt_rpow_const (p := (2:ℝ)^Real.sqrt 2) (Or.inl ht_pos.ne')
  convert this using 1

end Problems.Minif2f.amc12b_2021_p21
