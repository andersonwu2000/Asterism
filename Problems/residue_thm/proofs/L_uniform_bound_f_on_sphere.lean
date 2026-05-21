import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- uniform_bound_f_on_sphere: f analytic on punctured ball ⇒ ‖f‖ uniformly bounded on sphere R/2
-- via compactness + continuity, using IsCompact.exists_isMaxOn
theorem uniform_bound_f_on_sphere
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    ∃ C : ℝ, 0 ≤ C ∧ ∀ w ∈ Metric.sphere z₀ (R/2), ‖f w‖ ≤ C := by
  have hR2 : (0 : ℝ) < R / 2 := by linarith
  have hcomp : IsCompact (Metric.sphere z₀ (R/2)) := isCompact_sphere z₀ (R/2)
  have hnon : (Metric.sphere z₀ (R/2)).Nonempty := by
    refine ⟨z₀ + (R/2 : ℝ), ?_⟩
    simp; linarith
  have hsub : Metric.sphere z₀ (R/2) ⊆ Metric.ball z₀ R \ {z₀} := by
    intro w hw
    rw [Metric.mem_sphere] at hw
    constructor
    · rw [Metric.mem_ball]; linarith [hw.symm ▸ le_refl (R/2)]
    · simp only [Set.mem_singleton_iff]
      intro heq; simp [heq] at hw; linarith
  have hcont : ContinuousOn (fun w => ‖f w‖) (Metric.sphere z₀ (R/2)) :=
    (hf.continuousOn.mono hsub).norm
  obtain ⟨x, hx, hmax⟩ := hcomp.exists_isMaxOn hnon hcont
  exact ⟨‖f x‖, norm_nonneg _, fun w hw => hmax hw⟩

end Problems.residue_thm