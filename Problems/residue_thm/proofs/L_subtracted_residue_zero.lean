import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10299

namespace Problems.residue_thm

-- subtracted_residue_zero: residue of P - (res P a)/(z-a) at a is zero,
-- by linearity of circle integrals: ∮(P - c/(z-a)) = ∮P - c·2πi = 2πi·c - c·2πi = 0,
-- using s10299 for P and integral_sub_center_inv for the 1/(z-a) term.
theorem subtracted_residue_zero
    {P : ℂ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a})) :
    Complex.residue (fun z => P z - Complex.residue P a / (z - a)) a = 0 := by
  set c := Complex.residue P a with hc_def
  have h2pi : (2 * (Real.pi : ℂ) * Complex.I) ≠ 0 := by
    have hpi : (Real.pi : ℂ) ≠ 0 := by exact_mod_cast Real.pi_ne_zero
    exact mul_ne_zero (mul_ne_zero (by norm_num) hpi) Complex.I_ne_zero
  -- Analyticity of P on ball a 1 \ {a}
  have hP1 : AnalyticOn ℂ P (Metric.ball a 1 \ {a}) :=
    hP.mono (Set.diff_subset_diff_left (Set.subset_univ _))
  -- Analyticity of (z - a)⁻¹ on ball a 1 \ {a}
  have hinv : AnalyticOn ℂ (fun z => (z - a)⁻¹) (Metric.ball a 1 \ {a}) :=
    (analyticOn_id.sub analyticOn_const).inv
      (fun z hz => sub_ne_zero.mpr (fun h => hz.2 (Set.mem_singleton_iff.mpr h)))
  -- Analyticity of c * (z - a)⁻¹ on ball a 1 \ {a}
  have hcinv : AnalyticOn ℂ (fun z => c * (z - a)⁻¹) (Metric.ball a 1 \ {a}) :=
    analyticOn_const.mul hinv
  -- Analyticity of Q on ball a 1 \ {a}
  have hQ : AnalyticOn ℂ (fun z => P z - c / (z - a)) (Metric.ball a 1 \ {a}) := by
    have : (fun z => P z - c / (z - a)) = (fun z => P z - c * (z - a)⁻¹) := by
      ext z; ring
    rw [this]
    exact hP1.sub hcinv
  -- Use s10299 to express residue Q a via circle integral
  rw [show (fun z => P z - Complex.residue P a / (z - a)) =
        (fun z => P z - c / (z - a)) from rfl]
  rw [s10299 hQ (by norm_num : (0:ℝ) < 1/2) (by norm_num : (1:ℝ)/2 < 1)]
  -- Helper: Metric.sphere a (1/2) ⊆ ball a 1 \ {a}
  have hsph_sub : Metric.sphere a (1/2) ⊆ Metric.ball a 1 \ {a} := by
    intro z hz
    rw [Metric.mem_sphere] at hz
    refine ⟨Metric.mem_ball.mpr (by linarith), ?_⟩
    intro h
    simp only [Set.mem_singleton_iff] at h
    rw [h, dist_self] at hz
    norm_num at hz
  -- CircleIntegrability
  have hP_ci : CircleIntegrable P a (1/2) := by
    apply ContinuousOn.circleIntegrable (by norm_num)
    exact hP.continuousOn.mono
      (hsph_sub.trans (Set.diff_subset_diff_left (Set.subset_univ _)))
  have hinv_ci : CircleIntegrable (fun z => (z - a)⁻¹) a (1/2) := by
    apply ContinuousOn.circleIntegrable (by norm_num)
    exact hinv.continuousOn.mono hsph_sub
  have hcinv_ci : CircleIntegrable (fun z => c / (z - a)) a (1/2) := by
    have : (fun z => c / (z - a)) = (fun z => c * (z - a)⁻¹) := by ext z; ring
    rw [this]
    exact hinv_ci.const_mul c
  -- Split by linearity, then compute each circle integral
  have hsplit : (∮ z in C(a, 1/2), (P z - c / (z - a))) =
      (∮ z in C(a, 1/2), P z) - ∮ z in C(a, 1/2), c / (z - a) :=
    circleIntegral.integral_sub hP_ci hcinv_ci
  have hcinv_int : (∮ z in C(a, 1/2), c / (z - a)) = c * (2 * Real.pi * Complex.I) := by
    have : (∮ z in C(a, 1/2), c / (z - a)) = c * ∮ z in C(a, 1/2), (z - a)⁻¹ := by
      simp_rw [div_eq_mul_inv]
      exact circleIntegral.integral_const_mul c (fun z => (z - a)⁻¹) a (1/2)
    rw [this, circleIntegral.integral_sub_center_inv a (by norm_num : (1:ℝ)/2 ≠ 0)]
  have hP_int : (∮ z in C(a, 1/2), P z) = 2 * Real.pi * Complex.I * c := by
    have heq := s10299 hP1 (by norm_num : (0:ℝ) < 1/2) (by norm_num : (1:ℝ)/2 < 1)
    rw [← hc_def] at heq
    field_simp [h2pi] at heq
    linear_combination -heq
  -- Combine: (1/(2πi)) * (2πi*c - c*2πi) = 0
  rw [hsplit, hcinv_int, hP_int]
  field_simp [h2pi]
  ring

end Problems.residue_thm
