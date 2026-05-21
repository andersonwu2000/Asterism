import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_integrand_intvlint_outside
import Problems.residue_thm.proofs.L_circle_zeta_partial_aemeas_at_z
import Problems.residue_thm.proofs.L_circle_zeta_partial_hasderiv
import Problems.residue_thm.proofs.L_circle_zeta_partial_unif_bound_near

namespace Problems.residue_thm

open Filter Topology

-- Parametric Leibniz on the circle integral, unfolded to its interval-integral form
-- `∫ θ in 0..(2π), deriv(circleMap) θ • (g(circleMap θ) / (circleMap θ - ζ))`.
-- Neighborhood `s := Metric.ball z δ` with δ = (dist z c - r)/2 stays in the
-- "outside" region {ζ : r < dist ζ c}, ensuring the integrand and its ζ-derivative
-- remain finite. Sub-goals: integrand IntervalIntegrable (1), pointwise HasDerivAt
-- of integrand in ζ (2), and uniform sup-norm bound on the ζ-partial over the ball (3).
theorem s10442
    {g : ℂ → ℂ} {c : ℂ} {r : ℝ} (hr : 0 < r)
    (hg : ContinuousOn g (Metric.sphere c r))
    (z : ℂ) (hz : r < dist z c) :
    DifferentiableAt ℂ (fun ζ => ∮ w in C(c, r), g w / (w - ζ)) z  := by
  set δ : ℝ := (dist z c - r) / 2 with hδ_def
  have hδ_pos : 0 < δ := by rw [hδ_def]; linarith
  have hball_out : ∀ ζ ∈ Metric.ball z δ, r < dist ζ c := by
    intro ζ hζ
    have hdz : dist ζ z < δ := Metric.mem_ball.mp hζ
    have htri : dist z c ≤ dist z ζ + dist ζ c := dist_triangle z ζ c
    have hcomm : dist z ζ = dist ζ z := dist_comm _ _
    rw [hcomm] at htri
    linarith
  have hs_mem : Metric.ball z δ ∈ 𝓝 z := Metric.ball_mem_nhds z hδ_pos
  have h_integrable := circle_integrand_intvlint_outside hr hg
  have h_partial_meas := circle_zeta_partial_aemeas_at_z hr hg z hz
  have h_pointwise := @circle_zeta_partial_hasderiv g c r hr
  obtain ⟨M, h_bound⟩ := circle_zeta_partial_unif_bound_near hr hg z hz
  have h_meas_near : ∀ᶠ ζ in 𝓝 z, MeasureTheory.AEStronglyMeasurable
      (fun θ => deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ)))
      (MeasureTheory.volume.restrict (Set.uIoc (0:ℝ) (2 * Real.pi))) := by
    filter_upwards [hs_mem] with ζ hζ
    have h := (h_integrable ζ (hball_out ζ hζ)).aestronglyMeasurable
    rwa [Set.uIoc_of_le Real.two_pi_pos.le]
  have h_leibniz := intervalIntegral.hasDerivAt_integral_of_dominated_loc_of_deriv_le
    (𝕜 := ℂ) (a := (0:ℝ)) (b := 2 * Real.pi) (μ := MeasureTheory.volume)
    (s := Metric.ball z δ) (bound := fun _ => M)
    hs_mem h_meas_near (h_integrable z hz)
    h_partial_meas
    (by
      apply MeasureTheory.ae_of_all
      intro θ _hθ ζ hζ
      exact h_bound ζ hζ θ)
    intervalIntegrable_const
    (by
      apply MeasureTheory.ae_of_all
      intro θ _hθ ζ hζ
      exact h_pointwise θ ζ (hball_out ζ hζ))
  have hcast : (fun ζ => ∮ w in C(c, r), g w / (w - ζ)) =
               (fun ζ => ∫ θ in (0:ℝ)..(2 * Real.pi),
                          deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ))) := by
    funext ζ; rfl
  rw [hcast]
  exact h_leibniz.2.differentiableAt

end Problems.residue_thm
