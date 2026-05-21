import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cauchy_annulus_step_wrapper
import Problems.residue_thm.proofs.L_inner_principal_part_step_wrapper
import Problems.residue_thm.proofs.L_outer_holomorphic_step_wrapper
import Problems.residue_thm.proofs.L_q_eq_p_via_liouville

namespace Problems.residue_thm

-- Apply the inner Cauchy integral construction (`inner_principal_part_step_wrapper`)
-- at radius 1 to obtain P with cocompact decay + the inner-Cauchy formula.
-- Supplement with `outer_holomorphic_step_wrapper` + `cauchy_annulus_step_wrapper`
-- to get a holomorphic remainder g with Q = g + P on Metric.ball a 1 \ {a}.
-- The Liouville sub-goal `q_eq_p_via_liouville` then promotes Q = P globally on ℂ \ {a}:
-- the difference Q - P extends analytically across a (via g), is bounded
-- (both decay at cocompact), hence is constantly zero by Liouville.
theorem s10536
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0)) :
    ∃ (P : ℂ → ℂ) (R : ℝ),
      0 < R ∧
      AnalyticOn ℂ P (Set.univ \ {a}) ∧
      Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0) ∧
      (∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z))) ∧
      (∀ z ∈ Set.univ \ ({a} : Set ℂ), Q z = P z)  := by
  have hR : (0 : ℝ) < 1 := by norm_num
  have hQ_an_ball : AnalyticOn ℂ Q (Metric.ball a 1 \ {a}) :=
    hQ_an.mono (fun w hw => ⟨Set.mem_univ _, hw.2⟩)
  have h_inner := inner_principal_part_step_wrapper hR hQ_an_ball
  have h_outer := outer_holomorphic_step_wrapper hR hQ_an_ball
  obtain ⟨P, hP_an, hP_t, hP_eq⟩ := h_inner
  obtain ⟨g, hg_an, hg_eq⟩ := h_outer
  have hQg : ∀ w ∈ Metric.ball a 1 \ {a}, Q w = g w + P w :=
    cauchy_annulus_step_wrapper hR hQ_an_ball g P hg_eq hP_eq
  have h_diff_eq : ∀ w ∈ Metric.ball a 1 \ {a}, Q w - P w = g w := by
    intro w hw
    have hqw := hQg w hw
    linear_combination hqw
  have h_global : ∀ z ∈ Set.univ \ ({a} : Set ℂ), Q z = P z :=
    q_eq_p_via_liouville hR hQ_an hQ_decay hP_an hP_t hg_an h_diff_eq
  exact ⟨P, 1, hR, hP_an, hP_t, hP_eq, h_global⟩

end Problems.residue_thm
