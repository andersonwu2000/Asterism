import Mathlib

import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- x_clean_eq_orig_ae: ae_restrict_iff' + derivWithin_of_mem_nhds — for t ∈ Ioo 0 1,
-- Icc 0 1 ∈ nhds t so derivWithin (H τ') (Icc 0 1) t = deriv (H τ') t;
-- the two integrands agree on Ioo 0 1 (full measure in uIoc 0 1), giving a.e. equality.
theorem x_clean_eq_orig_ae
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1,
      (fun t => derivWithin
          (fun τ' => f (H τ' t) * derivWithin (H τ') (Set.Icc (0:ℝ) 1) t)
          (Set.Icc (0:ℝ) 1) τ)
        =ᵐ[MeasureTheory.volume.restrict (Set.uIoc (0:ℝ) 1)]
      (fun t => derivWithin
          (fun τ' => f (H τ' t) * deriv (H τ') t)
          (Set.Icc (0:ℝ) 1) τ) := by
    intro τ hτ
    rw [Filter.EventuallyEq, MeasureTheory.ae_restrict_iff' measurableSet_uIoc]
    filter_upwards [MeasureTheory.measure_eq_zero_iff_ae_notMem.mp
        (Real.volume_singleton (a := (1:ℝ)))] with t ht1
    intro htuIoc
    have htIoo : t ∈ Set.Ioo (0:ℝ) 1 := by
      rw [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)] at htuIoc
      exact ⟨htuIoc.1, htuIoc.2.lt_of_ne ht1⟩
    congr 1
    ext τ'
    congr 1
    exact derivWithin_of_mem_nhds (Icc_mem_nhds htIoo.1 htIoo.2)

end Problems.residue_thm
