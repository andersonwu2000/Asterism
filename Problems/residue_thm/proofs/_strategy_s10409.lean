import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cauchy_annulus_sum_formula
import Problems.residue_thm.proofs.L_inner_principal_part_exists
import Problems.residue_thm.proofs.L_outer_holomorphic_part_exists

namespace Problems.residue_thm

-- Cauchy two-radius Laurent-style split: outer Cauchy integral on radius `r > dist z z₀`
-- defines `g` analytic on `ball z₀ R`; inner Cauchy integral on radius `ε < dist z z₀`
-- defines `P` analytic on `ℂ \ {z₀}` with `P → 0` at ∞; the annular Cauchy formula on
-- the punctured ball glues them as `f z = g z + P z`.
--   * `outer_holomorphic_part_exists`: witnesses `g` via the outer-circle integral; analytic
--     by parametric Cauchy + radius-independence on the punctured ball.
--   * `inner_principal_part_exists`: witnesses `P` via the inner-circle integral; analytic
--     on the open complement of `{z₀}` and tendsto zero at infinity by `|f(w)|`-bound on
--     each fixed inner circle.
--   * `cauchy_annulus_sum_formula`: from the two value-equations on annular `r`,`ε`,
--     applies the Mathlib Cauchy-Goursat / Cauchy integral formula on the annulus to get
--     `f z = g z + P z` on the punctured ball.
-- Each sub-goal drops one of the three responsibilities (outer existence, inner
-- existence + asymptotics, glueing identity) so is strictly simpler than the joint
-- existential of the parent.
theorem s10409
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∃ (P g : ℂ → ℂ),
      AnalyticOn ℂ P (Set.univ \ {z₀}) ∧
      Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0) ∧
      AnalyticOn ℂ g (Metric.ball z₀ R) ∧
      ∀ z ∈ Metric.ball z₀ R \ {z₀}, f z = g z + P z  := by
  have h_g_exists := outer_holomorphic_part_exists hR hf
  have h_P_exists := inner_principal_part_exists hR hf
  obtain ⟨g, hg_an, hg_eq⟩ := h_g_exists
  obtain ⟨P, hP_an, hP_t, hP_eq⟩ := h_P_exists
  exact ⟨P, g, hP_an, hP_t, hg_an, cauchy_annulus_sum_formula hR hf g P hg_eq hP_eq⟩

end Problems.residue_thm
