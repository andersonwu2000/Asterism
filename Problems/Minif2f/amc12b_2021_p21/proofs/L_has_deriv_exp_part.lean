import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- has_deriv_exp_part: derivative of s ↦ √2^(2^s) via chain rule on HasDerivAt.rpow
-- Uses HasDerivAt.comp with hf : 2^s and hg : √2^v; both from HasDerivAt.rpow (const base).
theorem has_deriv_exp_part :
    ∀ t : ℝ, 3 < t →
      HasDerivAt (fun s : ℝ => Real.sqrt 2 ^ (2 : ℝ) ^ s)
        (Real.sqrt 2 ^ ((2 : ℝ) ^ t) * Real.log (Real.sqrt 2) *
          ((2 : ℝ) ^ t) * Real.log 2) t := by
  intro t ht
  have hf : HasDerivAt (fun s : ℝ => (2 : ℝ) ^ s) ((2 : ℝ) ^ t * Real.log 2) t := by
    have h := (hasDerivAt_const t (2 : ℝ)).rpow (hasDerivAt_id t) (by norm_num : (0:ℝ) < 2)
    simpa using h
  have hg : HasDerivAt (fun v : ℝ => Real.sqrt 2 ^ v)
      (Real.sqrt 2 ^ ((2 : ℝ) ^ t) * Real.log (Real.sqrt 2)) ((2 : ℝ) ^ t) := by
    have h := (hasDerivAt_const ((2:ℝ)^t) (Real.sqrt 2)).rpow (hasDerivAt_id ((2:ℝ)^t))
      (Real.sqrt_pos.mpr (by norm_num : (0:ℝ) < 2))
    simpa using h
  have hchain := hg.comp t hf
  convert hchain using 1
  ring

end Problems.Minif2f.amc12b_2021_p21
