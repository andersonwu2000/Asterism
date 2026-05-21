import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct application of Mathlib's `hasFPowerSeriesOn_cauchy_integral`.
-- Lift `r` to `ℝ≥0`, establish `CircleIntegrable f z₀ r` from analyticity on
-- the punctured ball (sphere of radius `r` lies in `ball z₀ R \ {z₀}`), then
-- the lemma yields `HasFPowerSeriesOnBall` in smul-form on `Metric.eball z₀ ↑r`;
-- `analyticOnNhd.analyticOn` lands `AnalyticOn`, and `AnalyticOn.congr` rewrites
-- the smul-kernel to the goal's `f w / (w - z)` form (pointwise `smul_eq_mul`
-- + `mul_comm` + `div_eq_mul_inv`).
theorem s10424
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {r : ℝ} (hr_pos : 0 < r) (hr_lt_R : r < R) :
    AnalyticOn ℂ (fun z => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
      ∮ w in C(z₀, r), f w / (w - z)) (Metric.ball z₀ r)  := by
  have hci : CircleIntegrable f z₀ r := by
    apply ContinuousOn.circleIntegrable hr_pos.le
    apply hf.continuousOn.mono
    intro w hw
    rw [Metric.mem_sphere] at hw
    refine ⟨?_, ?_⟩
    · rw [Metric.mem_ball, hw]; exact hr_lt_R
    · intro hw_eq
      rw [Set.mem_singleton_iff] at hw_eq
      subst hw_eq
      simp [dist_self] at hw
      linarith
  lift r to NNReal using hr_pos.le with r'
  have hr'_pos : (0 : NNReal) < r' := by exact_mod_cast hr_pos
  have hpow := hasFPowerSeriesOn_cauchy_integral hci hr'_pos
  have han : AnalyticOnNhd ℂ
      (fun w => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ • ∮ z in C(z₀, ↑r'), (z - w)⁻¹ • f z)
      (Metric.eball z₀ ↑r') := hpow.analyticOnNhd
  rw [Metric.eball_coe] at han
  refine (han.analyticOn).congr ?_
  intro z _
  simp [smul_eq_mul, div_eq_mul_inv, mul_comm]

end Problems.residue_thm
