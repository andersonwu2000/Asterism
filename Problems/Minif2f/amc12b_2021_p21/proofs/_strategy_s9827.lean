import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- Split into f1(t) = 2^t * log(√2) and f2(t) = 2^√2 * log t, apply ContinuousOn.sub.
-- f1 is rpow-of-constant-base times a constant. f2 is a constant times Real.log,
-- which is continuous on the interval since t ≥ 1 > 0.
theorem s9827 :
    ContinuousOn
      (fun t : ℝ => (2:ℝ)^t * Real.log (Real.sqrt 2)
            - (2:ℝ)^Real.sqrt 2 * Real.log t)
      (Set.Icc 1 (Real.sqrt 2))  := by
  apply ContinuousOn.sub
  · apply ContinuousOn.mul
    · apply Continuous.continuousOn
      exact continuous_const.rpow continuous_id' (fun _ => Or.inl (by norm_num))
    · exact continuousOn_const
  · apply ContinuousOn.mul continuousOn_const
    apply ContinuousOn.log continuousOn_id
    intro x hx
    simp only [id]
    have : (1:ℝ) ≤ x := hx.1
    linarith

end Problems.Minif2f.amc12b_2021_p21
