import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- p_eq_inner_integral_cocompact: cocompact eventually-equal via Filter.mem_cocompact + hP at ε=R/2
-- entry_kind: Builder
theorem p_eq_inner_integral_cocompact
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    P =ᶠ[Filter.cocompact ℂ]
      (fun z => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, R/2), f w / (w - z))) := by
  rw [Filter.eventuallyEq_iff_exists_mem]
  refine ⟨{z | R/2 < dist z z₀}, ?_, ?_⟩
  · rw [Filter.mem_cocompact]
    exact ⟨Metric.closedBall z₀ (R/2), isCompact_closedBall z₀ (R/2),
      fun z hz => by simp only [Set.mem_compl_iff, Metric.mem_closedBall, not_le] at hz; exact hz⟩
  · intro z hz
    simp only [Set.mem_setOf_eq] at hz
    have hzne : z ≠ z₀ := by
      intro h; subst h; simp at hz; linarith [half_pos hR]
    exact hP z hzne (R/2) (half_pos hR) hz (half_lt_self hR)

end Problems.residue_thm