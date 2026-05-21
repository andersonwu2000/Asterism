import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_int_q_eq_two_pi_residue_at
import Problems.residue_thm.proofs.L_path_int_p_eq_winding_circle_int_q
import Problems.residue_thm.proofs.L_uniform_eps_separation_path_radius

namespace Problems.residue_thm

-- Pick ε > 0 separating γ from a (uniform) and also satisfying ε < R, so
-- hP_rep is applicable along γ with the same ε. Reduce ∫₀¹ P(γt)·γ'(t) dt to
-- winding γ a · ∮_{C(a,ε)} Q via Fubini-swap + winding-locally-constant on the
-- inner circle, then evaluate ∮ Q over C(a,ε) as 2πi · residue Q a (radius
-- independence of the residue-defining circle); hQ_res = 0 collapses to 0.
-- Sub-goals:
--   (1) uniform_eps_separation_path_radius — Builder: compactness of γ([0,1])
--       supplies a uniform separation ε; min with R/2 keeps ε < R.
--   (2) path_int_p_eq_winding_circle_int_q — Backward: Fubini-swap circle/path
--       + windingNumber γ w constant on ball a ε.
--   (3) circle_int_q_eq_two_pi_residue_at — Builder: existing toolkit pattern
--       (cf. circle_int_eq_two_pi_residue) on Q analytic on punctured plane.
theorem s10535
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (hQ_res : Complex.residue Q a = 0)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t) = 0  := by
  obtain ⟨ε, hε_pos, hε_R, hε_sep⟩ :=
    uniform_eps_separation_path_radius hR hγ h_avoid
  have h_path_eq :=
    path_int_p_eq_winding_circle_int_q hR hQ_an hP hP_tendsto hP_rep hγ h_avoid hclosed
      hε_pos hε_R hε_sep
  have h_circle_eq :=
    circle_int_q_eq_two_pi_residue_at hQ_an hε_pos
  rw [h_path_eq, h_circle_eq, hQ_res]
  ring

end Problems.residue_thm
