import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10298

namespace Problems.residue_thm

-- circle_int_eq_two_pi_residue: circle integral of P at any ε equals 2πi·residue P a,
-- by unfolding the classical-choice residue definition and using s10298 for radius independence.
theorem circle_int_eq_two_pi_residue
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_repr : ∀ z : ℂ, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), P w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1)
    {ε : ℝ} (hε_pos : 0 < ε) :
    (∮ w in C(a, ε), P w) = 2 * Real.pi * Complex.I * Complex.residue P a := by
  have hPball : ∀ R : ℝ, 0 < R → AnalyticOn ℂ P (Metric.ball a R \ {a}) := fun R _ =>
    hP.mono (Set.diff_subset_diff_left (Set.subset_univ _))
  have hcond : ∃ R : ℝ, 0 < R ∧ AnalyticOn ℂ P (Metric.ball a R \ {a}) :=
    ⟨1, one_pos, hPball 1 one_pos⟩
  simp only [Complex.residue, dif_pos hcond]
  set R_chosen := Classical.choose hcond with hR_def
  have hR_spec := Classical.choose_spec hcond
  have hR_pos : 0 < R_chosen := hR_spec.1
  have hR_ball : AnalyticOn ℂ P (Metric.ball a R_chosen \ {a}) := hR_spec.2
  have h2pi_ne : 2 * (Real.pi : ℂ) * Complex.I ≠ 0 := by
    have hpi : (Real.pi : ℂ) ≠ 0 := by exact_mod_cast Real.pi_ne_zero
    exact mul_ne_zero (mul_ne_zero (by norm_num) hpi) Complex.I_ne_zero
  -- After simp, goal is: ∮ C(a,ε) P = 2πi * (1/(2πi) * ∮ C(a, R_chosen/2) P)
  -- Rewrite circle integral equality, then field-simplify the scalar
  have hcirc_eq : (∮ w in C(a, ε), P w) = (∮ w in C(a, R_chosen / 2), P w) := by
    by_cases hle : ε ≤ R_chosen / 2
    · exact s10298 hR_ball hε_pos hle (by linarith)
    · push Not at hle

      have hR2_pos : (0 : ℝ) < R_chosen / 2 := by linarith
      exact (s10298 (hPball (ε + 1) (by linarith)) hR2_pos (by linarith) (by linarith)).symm
  rw [hcirc_eq]
  field_simp [h2pi_ne]

end Problems.residue_thm
