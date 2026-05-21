import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_q_kernel_double_fubini_swap
import Problems.residue_thm.proofs.L_q_kernel_double_to_rhs
import Problems.residue_thm.proofs.L_q_kernel_lhs_to_double

namespace Problems.residue_thm

-- Fubini swap on Q-kernel: reduce circle integral to interval over [0, 2π], commute
-- with path integral over [0, 1] via joint integrability of the rational integrand,
-- then refold the circle integral on the other side.
--   (1) `q_kernel_lhs_to_double` — unfold ∮ on the LHS and pull `deriv γ t` inside.
--   (2) `q_kernel_double_fubini_swap` — swap order of integration on the double
--       interval integral (joint integrability of the rational integrand).
--   (3) `q_kernel_double_to_rhs` — pull `deriv (circleMap a ε) θ` inside, refold ∮.
theorem s10556
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
      = ∮ w in C(a, ε), Q w * (∫ t in (0:ℝ)..1, deriv γ t / (w - γ t))  := by
  have h_lhs :=
    q_kernel_lhs_to_double hR hQ_an hP hP_tendsto hP_rep hγ h_avoid hclosed hε_pos hε_R hε_sep
  have h_fubini :=
    q_kernel_double_fubini_swap hR hQ_an hP hP_tendsto hP_rep hγ h_avoid hclosed hε_pos hε_R hε_sep
  have h_rhs :=
    q_kernel_double_to_rhs hR hQ_an hP hP_tendsto hP_rep hγ h_avoid hclosed hε_pos hε_R hε_sep
  exact h_lhs.trans (h_fubini.trans h_rhs)

end Problems.residue_thm
