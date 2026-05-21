import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_q_kernel_integrand_integrable

namespace Problems.residue_thm

-- Fubini swap on the (t, θ)-double interval integral for the Q-kernel: reduce both
-- interval integrals to set integrals over `Set.Ioc`, apply `integral_integral_swap`
-- on the product measure, and refold back. Only non-trivial premise is joint
-- integrability of the rational integrand on the compact product `Ioc 0 1 × Ioc 0 (2π)`.
--   (1) `q_kernel_integrand_integrable` — joint integrability of
--       `(t, θ) ↦ deriv γ t * (deriv (circleMap a ε) θ •
--                              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))`
--       on the product of restricted Lebesgue measures.
theorem s10567
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_R : ε < R)
    (hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    (∫ t in (0:ℝ)..1, ∫ θ in (0:ℝ)..(2 * Real.pi),
        deriv γ t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))))
      = ∫ θ in (0:ℝ)..(2 * Real.pi), ∫ t in (0:ℝ)..1,
          deriv γ t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))  := by
  have h2pi : (0:ℝ) ≤ 2 * Real.pi := by positivity
  have hone : (0:ℝ) ≤ 1 := zero_le_one
  have h_int : MeasureTheory.Integrable
      (Function.uncurry (fun (t θ : ℝ) =>
        deriv γ t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))))
      ((MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) 1)).prod
       (MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) (2 * Real.pi)))) :=
    q_kernel_integrand_integrable hR hQ_an hP hP_tendsto hP_rep hγ h_avoid hclosed
      hε_pos hε_R hε_sep
  calc (∫ t in (0:ℝ)..1, ∫ θ in (0:ℝ)..(2 * Real.pi),
        deriv γ t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))))
      = ∫ t in (0:ℝ)..1, ∫ θ in Set.Ioc (0:ℝ) (2 * Real.pi),
          deriv γ t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))) ∂MeasureTheory.volume := by
        refine intervalIntegral.integral_congr (fun t _ => ?_)
        rw [intervalIntegral.integral_of_le h2pi]
    _ = ∫ t in Set.Ioc (0:ℝ) 1, ∫ θ in Set.Ioc (0:ℝ) (2 * Real.pi),
          deriv γ t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))
          ∂MeasureTheory.volume ∂MeasureTheory.volume := by
        rw [intervalIntegral.integral_of_le hone]
    _ = ∫ θ in Set.Ioc (0:ℝ) (2 * Real.pi), ∫ t in Set.Ioc (0:ℝ) 1,
          deriv γ t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))
          ∂MeasureTheory.volume ∂MeasureTheory.volume :=
        MeasureTheory.integral_integral_swap h_int
    _ = ∫ θ in Set.Ioc (0:ℝ) (2 * Real.pi), ∫ t in (0:ℝ)..1,
          deriv γ t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))) ∂MeasureTheory.volume := by
        refine MeasureTheory.setIntegral_congr_fun measurableSet_Ioc (fun θ _ => ?_)
        rw [intervalIntegral.integral_of_le hone]
    _ = ∫ θ in (0:ℝ)..(2 * Real.pi), ∫ t in (0:ℝ)..1,
          deriv γ t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))) := by
        rw [intervalIntegral.integral_of_le h2pi]

end Problems.residue_thm
