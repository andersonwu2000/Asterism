import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- q_kernel_double_to_rhs: unfold circle integral, factor constant from inner integral, ring-close
-- Unfolds ∮ as ∫ θ over [0,2π], then for each fixed θ rewrites the inner t-integrand
-- via ring to isolate (deriv circleMap · Q ·) as a multiplicative constant, pulls it out
-- of the t-integral via intervalIntegral.integral_const_mul, and closes by ring.
theorem q_kernel_double_to_rhs
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
    (∫ θ in (0:ℝ)..(2 * Real.pi), ∫ t in (0:ℝ)..1,
        deriv γ t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))))
      = ∮ w in C(a, ε), Q w * (∫ t in (0:ℝ)..1, deriv γ t / (w - γ t)) := by
  simp only [circleIntegral, smul_eq_mul]
  congr 1; ext θ
  have key : ∀ t : ℝ,
      deriv γ t * (deriv (circleMap a ε) θ * (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))) =
      (deriv (circleMap a ε) θ * Q (circleMap a ε θ)) * (deriv γ t / (circleMap a ε θ - γ t)) :=
    fun t => by ring
  simp_rw [key]
  have factored : ∫ t in (0:ℝ)..1,
      deriv (circleMap a ε) θ * Q (circleMap a ε θ) * (deriv γ t / (circleMap a ε θ - γ t)) =
      deriv (circleMap a ε) θ * Q (circleMap a ε θ) *
        ∫ t in (0:ℝ)..1, deriv γ t / (circleMap a ε θ - γ t) :=
    intervalIntegral.integral_const_mul _ _
  rw [factored]
  ring

end Problems.residue_thm
