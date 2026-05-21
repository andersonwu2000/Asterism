import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_integral_radius_indep_on_punctured_ball
import Problems.residue_thm.proofs._strategy_s10298

namespace Problems.residue_thm

-- slope_integral_diff_radius_indep: radius independence for (f w - f z)/(w - z) on annulus
-- dslope f z is analytic on ball z₀ R \ {z₀} via Complex.differentiableOn_dslope;
-- both circles miss z (ε < dist z z₀ < r), so integrals equal dslope integrals;
-- s10298 then gives the equality of the two dslope circle integrals.
set_option linter.unusedVariables false in
set_option linter.style.emptyLine false in
theorem slope_integral_diff_radius_indep

    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {z : ℂ} (hzB : z ∈ Metric.ball z₀ R) (hzNe : z ≠ z₀)
    {r : ℝ} (hr_lb : dist z z₀ < r) (hr_ub : r < R)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_lt_d : ε < dist z z₀) :
    (∮ w in C(z₀, r), (f w - f z) / (w - z))
      - (∮ w in C(z₀, ε), (f w - f z) / (w - z)) = 0 := by
  have hzB' : z ∈ Metric.ball z₀ R \ {z₀} := by
    simp only [Set.mem_diff, Set.mem_singleton_iff]; exact ⟨hzB, hzNe⟩
  have hopen : IsOpen (Metric.ball z₀ R \ {z₀}) :=
    Metric.isOpen_ball.sdiff isClosed_singleton
  have hdist_pos : 0 < dist z z₀ := dist_pos.mpr hzNe
  have hr_pos : 0 < r := lt_trans hdist_pos hr_lb

  have handslope : AnalyticOn ℂ (dslope f z) (Metric.ball z₀ R \ {z₀}) :=
    ((Complex.differentiableOn_dslope (hopen.mem_nhds hzB')).mpr
      hf.differentiableOn).analyticOn hopen
  have slope_eq : ∀ v : ℂ, v ≠ z →
      (f v - f z) / (v - z) = dslope f z v := fun v hvz => by
    simp only [dslope_of_ne _ hvz, slope, smul_eq_mul, vsub_eq_sub,
               div_eq_mul_inv, mul_comm]
  have heq_r : (∮ v in C(z₀, r), (f v - f z) / (v - z)) =
               ∮ v in C(z₀, r), dslope f z v :=
    circleIntegral.integral_congr hr_pos.le fun v hv => by
      rw [Metric.mem_sphere] at hv
      exact slope_eq v (fun heq => by rw [heq] at hv; linarith [dist_comm z₀ z])
  have heq_ε : (∮ v in C(z₀, ε), (f v - f z) / (v - z)) =
               ∮ v in C(z₀, ε), dslope f z v :=
    circleIntegral.integral_congr hε_pos.le fun v hv => by
      rw [Metric.mem_sphere] at hv
      exact slope_eq v (fun heq => by rw [heq] at hv; linarith [dist_comm z₀ z])
  rw [heq_r, heq_ε]
  exact sub_eq_zero.mpr
    (s10298 handslope hε_pos (le_of_lt (lt_trans hε_lt_d hr_lb)) hr_ub).symm

end Problems.residue_thm
