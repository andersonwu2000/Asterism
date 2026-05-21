import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10298

namespace Problems.residue_thm

-- circle_int_q_eq_two_pi_residue_at: circle integral of Q at any ε > 0 equals 2πi·residue Q a,
-- by unfolding the classical-choice residue definition and using s10298 for radius independence
-- (Q analytic on univ \ {a} restricts to any punctured ball).
theorem circle_int_q_eq_two_pi_residue_at
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {ε : ℝ} (hε_pos : 0 < ε) :
    (∮ w in C(a, ε), Q w) = 2 * Real.pi * Complex.I * Complex.residue Q a := by
  have hQball : ∀ R : ℝ, 0 < R → AnalyticOn ℂ Q (Metric.ball a R \ {a}) := fun R _ =>
    hQ_an.mono (Set.diff_subset_diff_left (Set.subset_univ _))
  have hcond : ∃ R : ℝ, 0 < R ∧ AnalyticOn ℂ Q (Metric.ball a R \ {a}) :=
    ⟨1, one_pos, hQball 1 one_pos⟩
  simp only [Complex.residue, dif_pos hcond]
  set R_chosen := Classical.choose hcond with hR_def
  have hR_spec := Classical.choose_spec hcond
  have hR_pos : 0 < R_chosen := hR_spec.1
  have h2pi_ne : 2 * (Real.pi : ℂ) * Complex.I ≠ 0 := by
    have hpi : (Real.pi : ℂ) ≠ 0 := by exact_mod_cast Real.pi_ne_zero
    exact mul_ne_zero (mul_ne_zero (by norm_num) hpi) Complex.I_ne_zero
  have hcirc_eq : (∮ w in C(a, ε), Q w) = (∮ w in C(a, R_chosen / 2), Q w) := by
    by_cases hle : ε ≤ R_chosen / 2
    · exact s10298 (hR_spec.2) hε_pos hle (by linarith)
    · push Not at hle
      have hR2_pos : (0 : ℝ) < R_chosen / 2 := by linarith
      exact (s10298 (hQball (ε + 1) (by linarith)) hR2_pos (by linarith) (by linarith)).symm
  rw [hcirc_eq]
  field_simp [h2pi_ne]

end Problems.residue_thm

