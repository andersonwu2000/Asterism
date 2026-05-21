import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- seg_integrand_integrable: continuity of f on ball (HasDerivAt → analyticOnNhd → continuous
-- derivative) + convexity of ball for segment MapsTo; close via intervalIntegrable_of_Icc.
theorem seg_integrand_integrable
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    {z w : ℂ}
    (hz : z ∈ Metric.ball z₀ R)
    (hw : w ∈ Metric.ball z₀ R) :
    IntervalIntegrable (fun t : ℝ => f (z + (t:ℂ) * (w - z)) * (w - z))
      MeasureTheory.volume 0 1 := by
  have hFdiff : DifferentiableOn ℂ F (Metric.ball z₀ R) :=
    fun z hz => (hF z hz).differentiableAt.differentiableWithinAt
  have hFnhd : AnalyticOnNhd ℂ F (Metric.ball z₀ R) :=
    hFdiff.analyticOnNhd Metric.isOpen_ball
  have hfcont : ContinuousOn f (Metric.ball z₀ R) := by
    apply (hFnhd.deriv_of_isOpen Metric.isOpen_ball).continuousOn.congr
    intro z hz
    exact (hF z hz).deriv.symm
  have hmaps : Set.MapsTo (fun t : ℝ => z + (t : ℂ) * (w - z)) (Set.Icc 0 1)
      (Metric.ball z₀ R) := by
    intro t ht
    have heq : z + (t : ℂ) * (w - z) = (1 - t) • z + t • w := by
      simp only [Complex.real_smul]; push_cast; ring
    change z + (t : ℂ) * (w - z) ∈ Metric.ball z₀ R
    rw [heq]
    exact (convex_ball z₀ R) hz hw (by linarith [ht.2]) ht.1 (by linarith)
  have hcont : ContinuousOn (fun t : ℝ => f (z + (t : ℂ) * (w - z)) * (w - z))
      (Set.Icc 0 1) :=
    (hfcont.comp
      (continuousOn_const.add (Complex.continuous_ofReal.continuousOn.mul continuousOn_const))
      hmaps).mul continuousOn_const
  exact hcont.intervalIntegrable_of_Icc (by norm_num)

end Problems.residue_thm
