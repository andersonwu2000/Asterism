import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- cell_quad_identity_on_ball: quadrilateral contour integral identity via primitive F on the
-- convex ball; each segment integral equals F(endpoint)−F(startpoint) by FTC, then ring closes.
theorem cell_quad_identity_on_ball
    {g : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hg : DifferentiableOn ℂ g (Metric.ball z₀ R))
    {z₁ z₂ z₃ z₄ : ℂ}
    (h₁ : z₁ ∈ Metric.ball z₀ R)
    (h₂ : z₂ ∈ Metric.ball z₀ R)
    (h₃ : z₃ ∈ Metric.ball z₀ R)
    (h₄ : z₄ ∈ Metric.ball z₀ R) :
    (∫ s in (0:ℝ)..1, g ((1 - (s:ℂ)) * z₁ + (s:ℂ) * z₄) * (z₄ - z₁))
    - (∫ s in (0:ℝ)..1, g ((1 - (s:ℂ)) * z₂ + (s:ℂ) * z₃) * (z₃ - z₂))
    =
    (∫ s in (0:ℝ)..1, g ((1 - (s:ℂ)) * z₁ + (s:ℂ) * z₂) * (z₂ - z₁))
    - (∫ s in (0:ℝ)..1, g ((1 - (s:ℂ)) * z₄ + (s:ℂ) * z₃) * (z₃ - z₄)) := by
  obtain ⟨F, hF⟩ := hg.isExactOn_ball
  suffices hseg : ∀ a b : ℂ, a ∈ Metric.ball z₀ R → b ∈ Metric.ball z₀ R →
      (∫ s in (0:ℝ)..1, g ((1 - (s:ℂ)) * a + (s:ℂ) * b) * (b - a)) = F b - F a by
    rw [hseg z₁ z₄ h₁ h₄, hseg z₂ z₃ h₂ h₃, hseg z₁ z₂ h₁ h₂, hseg z₄ z₃ h₄ h₃]
    ring
  intro a b ha hb
  have heq : ∀ s : ℝ, (1 - (s:ℂ)) * a + (s:ℂ) * b = a + (s:ℂ) * (b - a) := fun s => by ring
  simp_rw [heq]
  have hmem : Set.MapsTo (fun t : ℝ => a + (t:ℂ) * (b - a)) (Set.Icc 0 1)
      (Metric.ball z₀ R) := by
    intro t ht
    change a + (t:ℂ) * (b - a) ∈ Metric.ball z₀ R
    have h : (1 - (t:ℝ)) • a + (t:ℝ) • b ∈ Metric.ball z₀ R :=
      (convex_ball z₀ R) ha hb (sub_nonneg.mpr ht.2) ht.1 (by linarith [ht.1, ht.2])
    simp only [RCLike.real_smul_eq_coe_mul] at h
    have heq2 : ((1 - (t:ℝ) : ℝ) : ℂ) * a + ((t:ℝ) : ℂ) * b = a + (t:ℂ) * (b - a) := by
      push_cast; ring
    rwa [← heq2]
  have h_cont : ContinuousOn (fun t : ℝ => F (a + (t:ℂ) * (b - a))) (Set.Icc 0 1) := by
    apply ContinuousOn.comp
    · exact DifferentiableOn.continuousOn
        (fun x hx => (hF x hx).differentiableAt.differentiableWithinAt)
    · exact (by fun_prop : Continuous (fun t : ℝ => a + (t:ℂ) * (b - a))).continuousOn
    · exact hmem
  have h_deriv : ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivAt (fun t : ℝ => F (a + (t:ℂ) * (b - a)))
        (g (a + (t:ℂ) * (b - a)) * (b - a)) t := by
    intro t ht
    have hmemI : a + (t:ℂ) * (b - a) ∈ Metric.ball z₀ R := hmem ⟨ht.1.le, ht.2.le⟩
    have hFder := hF _ hmemI
    have hGs : HasDerivAt (fun s : ℂ => a + s * (b - a)) (b - a) (t:ℂ) := by
      have h1 := (hasDerivAt_id (t:ℂ)).mul_const (b - a)
      simp only [one_mul] at h1
      exact h1.const_add a
    exact (hFder.comp (t:ℂ) hGs).comp_ofReal
  have h_int : IntervalIntegrable (fun t : ℝ => g (a + (t:ℂ) * (b - a)) * (b - a))
      MeasureTheory.volume 0 1 := by
    have hFdiff : DifferentiableOn ℂ F (Metric.ball z₀ R) :=
      fun z hz => (hF z hz).differentiableAt.differentiableWithinAt
    have hFnhd : AnalyticOnNhd ℂ F (Metric.ball z₀ R) :=
      hFdiff.analyticOnNhd Metric.isOpen_ball
    have hgcont : ContinuousOn g (Metric.ball z₀ R) := by
      apply (hFnhd.deriv_of_isOpen Metric.isOpen_ball).continuousOn.congr
      intro z hz; exact (hF z hz).deriv.symm
    exact ((hgcont.comp
      (continuousOn_const.add
        (Complex.continuous_ofReal.continuousOn.mul continuousOn_const))
      hmem).mul continuousOn_const).intervalIntegrable_of_Icc (by norm_num)
  have h_ftc := intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le
    (a := 0) (b := 1) zero_le_one h_cont h_deriv h_int
  have h0 : a + ((0:ℝ):ℂ) * (b - a) = a := by push_cast; ring
  have h1 : a + ((1:ℝ):ℂ) * (b - a) = b := by push_cast; ring
  rw [h0, h1] at h_ftc
  exact h_ftc

end Problems.residue_thm
