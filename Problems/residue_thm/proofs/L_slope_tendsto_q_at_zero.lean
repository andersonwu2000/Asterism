import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- slope_tendsto_q_at_zero: Filter.Tendsto congr + integral_smul_const closes slope = avg-integral
-- entry_kind: Builder

theorem slope_tendsto_q_at_zero
    {Q : ℂ → ℂ} {a : ℂ} {F : ℂ → ℂ} (z : ℂ)
    (hzne : z ≠ a)
    (h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h)
    (h_avg : Filter.Tendsto (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h))
      (nhds 0) (nhds (Q z))) :
    Filter.Tendsto (fun t : ℂ => t⁻¹ • (F (z + t) - F z))
      (nhdsWithin 0 ({0}ᶜ : Set ℂ)) (nhds (Q z)) := by
    apply (h_avg.mono_left nhdsWithin_le_nhds).congr'
    filter_upwards [nhdsWithin_le_nhds (Metric.ball_mem_nhds 0 (dist_pos.mpr hzne)),
      self_mem_nhdsWithin] with t ht_ball ht_ne
    simp only [Set.mem_compl_singleton_iff] at ht_ne
    symm
    rw [h_seg t (by simpa [Metric.mem_ball, dist_zero_right] using ht_ball)]
    simp only [smul_eq_mul]
    have hinteg : ∫ (s : ℝ) in (0:ℝ)..1, Q (z + (s:ℂ) * t) * t =
                  (∫ (s : ℝ) in (0:ℝ)..1, Q (z + (s:ℂ) * t)) * t := by
      simp_rw [← smul_eq_mul (Q _) t]
      exact intervalIntegral.integral_smul_const _ _
    rw [hinteg]
    field_simp [ht_ne]



end Problems.residue_thm
