import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- chord_segment_form_primdiff: FTC for F∘(s↦z+s·(w-z)) on [0,1]; segment in ball via convexity;
-- chain rule via HasDerivAt.comp_ofReal; three FTC ingredients inlined from proved sub-goals.
theorem chord_segment_form_primdiff
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    {z w : ℂ}
    (hz : z ∈ Metric.ball z₀ R)
    (hw : w ∈ Metric.ball z₀ R) :
    (∫ s in (0:ℝ)..1, f (z + (s:ℂ) * (w - z)) * (w - z)) = F w - F z := by
  have h_cont : ContinuousOn (fun t : ℝ => F (z + (t:ℂ) * (w - z))) (Set.Icc 0 1) := by
    apply ContinuousOn.comp
    · exact (DifferentiableOn.continuousOn
        (fun x hx => (hF x hx).differentiableAt.differentiableWithinAt))
    · exact (by fun_prop : Continuous (fun t : ℝ => z + (t : ℂ) * (w - z))).continuousOn
    · intro t ht
      exact (convex_ball z₀ R).add_smul_sub_mem hz hw ht
  have h_deriv : ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivAt (fun t : ℝ => F (z + (t:ℂ) * (w - z)))
        (f (z + (t:ℂ) * (w - z)) * (w - z)) t := by
    intro t ht
    have hmem : z + (t:ℂ) * (w - z) ∈ Metric.ball z₀ R := by
      have h : (1 - (t:ℝ)) • z + (t:ℝ) • w ∈ Metric.ball z₀ R :=
        (convex_ball z₀ R) hz hw (sub_nonneg.mpr ht.2.le) ht.1.le (by ring)
      simp only [RCLike.real_smul_eq_coe_mul] at h
      have heq : ((1 - (t:ℝ) : ℝ) : ℂ) * z + ((t:ℝ) : ℂ) * w = z + (t:ℂ) * (w - z) := by
        push_cast; ring
      rw [← heq]; exact h
    have hFder : HasDerivAt F (f (z + ↑t * (w - z))) (z + ↑t * (w - z)) := hF _ hmem
    have hGs : HasDerivAt (fun s : ℂ => z + s * (w - z)) (w - z) (t : ℂ) := by
      have h1 : HasDerivAt (fun s : ℂ => s * (w - z)) (1 * (w - z)) (t : ℂ) :=
        (hasDerivAt_id (t : ℂ)).mul_const (w - z)
      simp only [one_mul] at h1
      exact h1.const_add z
    exact (hFder.comp (t : ℂ) hGs).comp_ofReal
  have h_int : IntervalIntegrable (fun t : ℝ => f (z + (t:ℂ) * (w - z)) * (w - z))
      MeasureTheory.volume 0 1 := by
    have hFdiff : DifferentiableOn ℂ F (Metric.ball z₀ R) :=
      fun x hx => (hF x hx).differentiableAt.differentiableWithinAt
    have hFnhd : AnalyticOnNhd ℂ F (Metric.ball z₀ R) :=
      hFdiff.analyticOnNhd Metric.isOpen_ball
    have hfcont : ContinuousOn f (Metric.ball z₀ R) := by
      apply (hFnhd.deriv_of_isOpen Metric.isOpen_ball).continuousOn.congr
      intro x hx
      exact (hF x hx).deriv.symm
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
        (continuousOn_const.add
          (Complex.continuous_ofReal.continuousOn.mul continuousOn_const))
        hmaps).mul continuousOn_const
    exact hcont.intervalIntegrable_of_Icc (by norm_num)
  have h_ftc := intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le
    (a := 0) (b := 1) zero_le_one h_cont h_deriv h_int
  have h0 : z + ((0:ℝ):ℂ) * (w - z) = z := by push_cast; ring
  have h1 : z + ((1:ℝ):ℂ) * (w - z) = w := by push_cast; ring
  rw [h0, h1] at h_ftc
  exact h_ftc

end Problems.residue_thm

