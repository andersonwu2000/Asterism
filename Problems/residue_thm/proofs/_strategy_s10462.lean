import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_int_eq_two_pi_residue
import Problems.residue_thm.proofs.L_exists_path_avoid_radius
import Problems.residue_thm.proofs.L_path_int_eq_winding_circle_int

namespace Problems.residue_thm

-- Three-step decomposition: separate, integrate by Cauchy repr, recognize residue.
--   (1) `exists_path_avoid_radius` — by compactness of γ(Icc) + h_avoid, choose ε > 0
--       with ε < dist (γ t) a for all t.
--   (2) `path_int_eq_winding_circle_int` — using hP_repr at every γ t plus Fubini and
--       the winding-number formula, rewrite ∫₀¹ P(γ t)·γ'(t) dt = winding · ∮_{C(a,ε)} P.
--   (3) `circle_int_eq_two_pi_residue` — for any ε > 0, ∮_{C(a,ε)} P = 2πi · residue P a
--       via residue_eq_circle_integral (P analytic on univ \ {a} ⇒ on ball a (ε+1) \ {a}).
theorem s10462
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_repr : ∀ z : ℂ, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), P w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t) =
      2 * Real.pi * Complex.I *
        ((Complex.windingNumber γ a : ℂ) * Complex.residue P a)  := by
  obtain ⟨ε, hε_pos, hε_sep⟩ :=
    exists_path_avoid_radius hP hP_tendsto hP_repr hγ h_avoid hclosed
  have h_path := path_int_eq_winding_circle_int hP hP_tendsto hP_repr hγ h_avoid hclosed
    hε_pos hε_sep
  have h_circ := circle_int_eq_two_pi_residue hP hP_tendsto hP_repr hγ h_avoid hclosed
    hε_pos
  rw [h_path, h_circ]; ring
end Problems.residue_thm
