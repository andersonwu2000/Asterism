import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- Direct differentiation: HasDerivAt of 2^s via `(hasDerivAt_const).rpow (hasDerivAt_id) h_pos`
-- (lessons #5), HasDerivAt of log s via `Real.hasDerivAt_log` (requires t ≠ 0, supplied from
-- 1 < t via `Set.Ioo` membership). Combine with `.mul_const`, `.const_mul`, then `.sub`.
theorem s9830 :
    ∀ t ∈ Set.Ioo (1:ℝ) (Real.sqrt 2),
      HasDerivAt
        (fun s : ℝ => (2:ℝ)^s * Real.log (Real.sqrt 2)
                - (2:ℝ)^Real.sqrt 2 * Real.log s)
        ((2:ℝ)^t * Real.log 2 * Real.log (Real.sqrt 2)
          - (2:ℝ)^Real.sqrt 2 * t⁻¹) t  := by
  intro t ht
  have ht_pos : (0:ℝ) < t := lt_trans zero_lt_one ht.1
  have ht_ne : t ≠ 0 := ht_pos.ne'
  have h_two_pos : (0:ℝ) < 2 := by norm_num
  have h_exp : HasDerivAt (fun s : ℝ => (2:ℝ)^s) ((2:ℝ)^t * Real.log 2) t := by
    simpa using (hasDerivAt_const t (2:ℝ)).rpow (hasDerivAt_id t) h_two_pos
  have h_log : HasDerivAt (fun s : ℝ => Real.log s) (t⁻¹) t := Real.hasDerivAt_log ht_ne
  have h1 : HasDerivAt (fun s : ℝ => (2:ℝ)^s * Real.log (Real.sqrt 2))
      ((2:ℝ)^t * Real.log 2 * Real.log (Real.sqrt 2)) t :=
    h_exp.mul_const (Real.log (Real.sqrt 2))
  have h2 : HasDerivAt (fun s : ℝ => (2:ℝ)^Real.sqrt 2 * Real.log s)
      ((2:ℝ)^Real.sqrt 2 * t⁻¹) t :=
    h_log.const_mul ((2:ℝ)^Real.sqrt 2)
  exact h1.sub h2

end Problems.Minif2f.amc12b_2021_p21
