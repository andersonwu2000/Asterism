import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_analytic_integrand_interval_integrable
import Problems.residue_thm.proofs.L_closed_glued_primitive_from_ball_cover

namespace Problems.residue_thm

-- FTC-with-closed-primitive route: build a glued path primitive F : ℝ → ℂ from
-- per-ball local primitives along the cover, with telescoping constants so F is
-- continuous on [0,1] and HasDerivAt at each interior t; closedness γ 0 = γ 1
-- propagates to F 0 = F 1. The integrand is interval-integrable from continuity
-- of g (analytic ⇒ continuous) composed with γ. FTC then collapses the integral
-- to F 1 - F 0 = 0.
--
-- Sub-goals (both strictly simpler than the path-integral equality):
--   * analytic_integrand_interval_integrable — Builder, pure regularity of g∘γ·γ'.
--   * closed_glued_primitive_from_ball_cover — Backward, the analytic monodromy
--     + telescoping core (cites the proved closed_path_integral_zero_on_ball
--     route via local primitives `DifferentiableOn.isExactOn_ball`).
theorem s10495
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1)
    {n : ℕ} {t : ℕ → ℝ} {c : ℕ → ℂ} {r : ℕ → ℝ}
    (ht0 : t 0 = 0)
    (htn : t n = 1)
    (hmono : ∀ i, i < n → t i ≤ t (i + 1))
    (hpos : ∀ i, i < n → 0 < r i)
    (hball : ∀ i, i < n → Metric.ball (c i) (r i) ⊆ U)
    (hseg : ∀ i, i < n →
      Set.MapsTo γ (Set.Icc (t i) (t (i + 1))) (Metric.ball (c i) (r i))) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0  := by
  have h_int : IntervalIntegrable (fun t => g (γ t) * deriv γ t)
      MeasureTheory.volume 0 1 :=
    analytic_integrand_interval_integrable hU hg hγ hmaps
  obtain ⟨F, hF_cont, hF_deriv, hF_closed⟩ :=
    closed_glued_primitive_from_ball_cover hU hg hγ hmaps hclosed
      ht0 htn hmono hpos hball hseg
  rw [intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le zero_le_one hF_cont hF_deriv h_int,
      ← hF_closed, sub_self]

end Problems.residue_thm
