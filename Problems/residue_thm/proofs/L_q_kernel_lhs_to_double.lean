import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- q_kernel_lhs_to_double: unfold circle integral on LHS pointwise and pull scalar deriv γ t inside
-- via circleIntegral definition + intervalIntegral.integral_const_mul
theorem q_kernel_lhs_to_double
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
    (∫ t in (0:ℝ)..1, deriv γ t * (∮ w in C(a, ε), Q w / (w - γ t)))
      = ∫ t in (0:ℝ)..1, ∫ θ in (0:ℝ)..(2 * Real.pi),
          deriv γ t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))) := by
  congr 1
  ext t
  simp only [circleIntegral, smul_eq_mul]
  exact (intervalIntegral.integral_const_mul (deriv γ t) _).symm

end Problems.residue_thm
