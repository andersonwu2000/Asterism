import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- cocompact_eventually_far_from_z0: IsCompact.compl_mem_cocompact on closedBall z₀ (R/2) gives
-- the cocompact-eventual bound R/2 < ‖z - z₀‖; membership follows from Complex.dist_eq.
theorem cocompact_eventually_far_from_z0
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)))
    (C : ℝ) (hC0 : 0 ≤ C)
    (hC : ∀ w ∈ Metric.sphere z₀ (R/2), ‖f w‖ ≤ C) :
    ∀ᶠ z in Filter.cocompact ℂ, R/2 < ‖z - z₀‖ := by
  apply Filter.mem_of_superset (isCompact_closedBall z₀ (R/2)).compl_mem_cocompact
  intro z hz
  simp only [Set.mem_compl_iff, Metric.mem_closedBall, not_le] at hz
  simp only [Set.mem_setOf_eq]
  rwa [← Complex.dist_eq]
end Problems.residue_thm
