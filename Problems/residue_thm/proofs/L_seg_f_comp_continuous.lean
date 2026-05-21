import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- seg_f_comp_continuous: ContinuousOn.comp + Convex.add_smul_sub_mem; F continuous via HasDerivAt,
-- segment in ball via convexity of ball
theorem seg_f_comp_continuous
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    {z w : ℂ}
    (hz : z ∈ Metric.ball z₀ R)
    (hw : w ∈ Metric.ball z₀ R) :
    ContinuousOn (fun t : ℝ => F (z + (t:ℂ) * (w - z))) (Set.Icc 0 1) := by
  apply ContinuousOn.comp
  · exact (DifferentiableOn.continuousOn
      (fun x hx => (hF x hx).differentiableAt.differentiableWithinAt))
  · exact (by fun_prop : Continuous (fun t : ℝ => z + (t : ℂ) * (w - z))).continuousOn
  · intro t ht
    exact (convex_ball z₀ R).add_smul_sub_mem hz hw ht

end Problems.residue_thm
