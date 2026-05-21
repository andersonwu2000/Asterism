import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- hasderivat_from_avg_and_seg: isLittleO bridge — segment identity + avg limit → HasDerivAt.
-- Rewrites via hasDerivAt_iff_isLittleO_nhds_zero; factors constant h from the interval
-- integral via intervalIntegral.integral_smul; then the avg-minus-Qz norm bound closes.
theorem hasderivat_from_avg_and_seg
    {Q : ℂ → ℂ} {a : ℂ} {F : ℂ → ℂ} (z : ℂ)
    (hzne : z ≠ a)
    (h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h)
    (h_avg : Filter.Tendsto (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h))
      (nhds 0) (nhds (Q z))) :
    HasDerivAt F (Q z) z := by
  rw [hasDerivAt_iff_isLittleO_nhds_zero]
  rw [Asymptotics.isLittleO_iff]
  intro c hc
  have havg_ev : ∀ᶠ h : ℂ in nhds 0,
      ‖(∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h)) - Q z‖ < c := by
    have := h_avg.eventually (Metric.ball_mem_nhds (Q z) hc)
    filter_upwards [this] with h hh
    rwa [dist_eq_norm] at hh
  have hsmall_ev : ∀ᶠ h : ℂ in nhds 0, ‖h‖ < dist z a := by
    filter_upwards [Metric.ball_mem_nhds (0 : ℂ) (dist_pos.mpr hzne)] with h hh
    rwa [Metric.mem_ball, dist_zero_right] at hh
  filter_upwards [havg_ev, hsmall_ev] with h havg hlt
  by_cases hh : h = 0
  · simp [hh]
  · have hfact : ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h =
        (∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h)) * h := by
      simp_rw [show ∀ t : ℝ, Q (z + (t : ℂ) * h) * h = h • Q (z + (t : ℂ) * h) from
        fun t => by ring]
      rw [intervalIntegral.integral_smul]; ring
    have heq : F (z + h) - F z - h • Q z =
        ((∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h)) - Q z) * h := by
      rw [smul_eq_mul, h_seg h hlt, hfact]; ring
    rw [heq, norm_mul]
    nlinarith [norm_nonneg h, havg.le]

end Problems.residue_thm

