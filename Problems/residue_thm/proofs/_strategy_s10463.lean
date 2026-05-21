import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cauchy_annulus_sum_formula_wrapper
import Problems.residue_thm.proofs.L_inner_principal_part_exists_wrapper
import Problems.residue_thm.proofs.L_inner_principal_part_unique
import Problems.residue_thm.proofs.L_outer_holomorphic_part_exists_wrapper

namespace Problems.residue_thm

-- Liouville-style identification: P = its own principal part at a.
-- Apply the proved inner/outer toolkit (via wrappers) at radius R := dist z a + 1
-- (so ε is automatically valid). `inner_principal_part_exists_wrapper` yields Q
-- with the Cauchy integral formula; `outer_holomorphic_part_exists_wrapper` +
-- `cauchy_annulus_sum_formula_wrapper` glue P = g + Q on the punctured ball, with
-- g analytic across a. The Backward sub-goal `inner_principal_part_unique` is the
-- Liouville core (an entire function tending to 0 at cocompact is zero, applied
-- to P - Q extended by g across a), giving P = Q on univ \ {a}; substituting
-- closes the goal via Q's integral formula.
theorem s10463
    {P : ℂ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0)) :
    ∀ z : ℂ, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a →
      P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(a, ε), P w / (w - z))  := by
  intro z hzNe ε hε_pos hε_lt_d
  have hd_pos : 0 < dist z a := dist_pos.mpr hzNe
  set R : ℝ := dist z a + 1 with hR_def
  have hR_pos : (0 : ℝ) < R := by
    have := dist_nonneg (x := z) (y := a)
    simp [hR_def]; linarith
  have hε_lt_R : ε < R := by simp [hR_def]; linarith
  have hP_ball : AnalyticOn ℂ P (Metric.ball a R \ {a}) :=
    hP.mono (fun w hw => ⟨trivial, hw.2⟩)
  obtain ⟨Q, hQ_an, hQ_tendsto, hQ_repr⟩ :=
    inner_principal_part_exists_wrapper hR_pos hP_ball
  obtain ⟨g, hg_an, hg_eq⟩ :=
    outer_holomorphic_part_exists_wrapper hR_pos hP_ball
  have h_glue : ∀ z' ∈ Metric.ball a R \ {a}, P z' = g z' + Q z' :=
    cauchy_annulus_sum_formula_wrapper hR_pos hP_ball g Q hg_eq hQ_repr
  have h_PQ : ∀ w, w ≠ a → P w = Q w :=
    inner_principal_part_unique hR_pos hP hP_tendsto hQ_an hQ_tendsto hg_an
      (fun w hw => by
        have hg := h_glue w hw
        linear_combination hg)
  rw [h_PQ z hzNe]
  exact hQ_repr z hzNe ε hε_pos hε_lt_d hε_lt_R

end Problems.residue_thm
