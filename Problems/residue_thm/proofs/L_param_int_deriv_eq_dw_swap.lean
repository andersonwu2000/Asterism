import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- param_int_deriv_eq_dw_swap: swap deriv for derivWithin in integral via a.e. equality
-- Integrands differ only at t=1 (measure zero); derivWithin_of_mem_nhds handles interior points.
-- entry_kind: Builder
theorem param_int_deriv_eq_dw_swap
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hr : 0 < r)
    (_h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, r < dist (γ t) z) :
    ∀ w ∈ Metric.ball z r,
      (∫ t in (0:ℝ)..1, deriv γ t / (γ t - w)) =
      (∫ t in (0:ℝ)..1, derivWithin γ (Set.Icc 0 1) t / (γ t - w)) := by
  intro w _hw
  apply intervalIntegral.integral_congr_ae
  simp only [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)]
  rw [MeasureTheory.ae_iff]
  apply MeasureTheory.measure_mono_null _ (Real.volume_singleton (a := 1))
  intro t ht
  simp only [Set.mem_setOf_eq, Classical.not_imp] at ht
  obtain ⟨ht_mem, ht_ne⟩ := ht
  simp only [Set.mem_singleton_iff]
  by_contra h1
  exact ht_ne (by
    congr 1
    have htIoo : t ∈ Set.Ioo (0:ℝ) 1 := ⟨ht_mem.1, lt_of_le_of_ne ht_mem.2 h1⟩
    exact (derivWithin_of_mem_nhds (Icc_mem_nhds htIoo.1 htIoo.2)).symm)

end Problems.residue_thm
