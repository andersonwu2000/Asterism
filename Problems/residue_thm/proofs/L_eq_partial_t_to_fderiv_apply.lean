import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- eq_partial_t_to_fderiv_apply: deriv (H p.1) p.2 = fderiv ℝ (H ·.1 ·.2) p (0,1) on
-- Ioo×Ioo interior; proved via HasDerivAt chain rule: compose HasFDerivAt G with
-- HasDerivAt (t ↦ (p.1, t)) (0,1), yielding HasDerivAt (H p.1) (fderiv G p (0,1)).
-- entry_kind: Builder
theorem eq_partial_t_to_fderiv_apply
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ p ∈ Set.Ioo (0:ℝ) 1 ×ˢ Set.Ioo (0:ℝ) 1,
      deriv (H p.1) p.2 =
        fderiv ℝ (fun q : ℝ × ℝ => H q.1 q.2) p (0, 1) := by
    intro p hp
    obtain ⟨hpτ, hpt⟩ := hp
    set G := fun q : ℝ × ℝ => H q.1 q.2 with hG_def
    have hGdiff : HasFDerivAt G (fderiv ℝ G p) p := by
      apply DifferentiableAt.hasFDerivAt
      apply (hH.differentiableOn (by norm_num)).differentiableAt
      exact Filter.mem_of_superset
        ((IsOpen.prod isOpen_Ioo isOpen_Ioo).mem_nhds (Set.mk_mem_prod hpτ hpt))
        (Set.prod_mono Set.Ioo_subset_Icc_self Set.Ioo_subset_Icc_self)
    have hφdiff : HasDerivAt (fun t => (p.1, t)) (0, 1) p.2 := by
      exact (hasDerivAt_const p.2 p.1).prodMk (hasDerivAt_id p.2)
    have hcompdiff : HasDerivAt (H p.1) (fderiv ℝ G p (0, 1)) p.2 := by
      have h := hGdiff.comp_hasDerivAt p.2 hφdiff
      simp only [hG_def] at h
      exact h
    exact hcompdiff.deriv

end Problems.residue_thm
