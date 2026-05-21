import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- hasderivat_from_avg_seg_inlined: HasDerivAt via segment-average tendsto;
-- uses hasDerivAt_iff_tendsto_slope_zero + integral_const_mul to rewrite
-- h⁻¹·(F(z+h)-F(z)) = ∫Q(z+t·h)dt, then closes by h_avg.
theorem hasderivat_from_avg_seg_inlined
    {Q : ℂ → ℂ} {a : ℂ} {F : ℂ → ℂ} (z : ℂ)
    (hzne : z ≠ a)
    (h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h)
    (h_avg : Filter.Tendsto (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h))
      (nhds 0) (nhds (Q z))) :
    HasDerivAt F (Q z) z := by
  rw [hasDerivAt_iff_tendsto_slope_zero]
  have hdist : 0 < dist z a := dist_pos.mpr hzne
  apply (h_avg.mono_left nhdsWithin_le_nhds).congr'
  filter_upwards [nhdsWithin_le_nhds (Metric.ball_mem_nhds (0 : ℂ) hdist),
                  self_mem_nhdsWithin] with h hlt hne
  simp only [Set.mem_compl_iff, Set.mem_singleton_iff] at hne
  simp only [Metric.mem_ball, dist_zero_right] at hlt
  simp only [smul_eq_mul]
  have hh := h_seg h hlt
  rw [hh]
  simp_rw [mul_comm (Q _) h]
  have hint : ∫ t in (0:ℝ)..1, h * Q (z + (t:ℂ) * h) =
              h * ∫ t in (0:ℝ)..1, Q (z + (t:ℂ) * h) :=
    intervalIntegral.integral_const_mul h _
  rw [hint, ← mul_assoc, inv_mul_cancel₀ hne, one_mul]


end Problems.residue_thm