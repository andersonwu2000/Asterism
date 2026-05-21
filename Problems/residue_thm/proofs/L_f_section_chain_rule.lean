import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- f_section_chain_rule: HasDerivAt chain rule (ContDiffOn section + AnalyticOn) for t ↦ f(H τ t)
-- Extract C¹ section H τ via ContDiffOn.comp with the constant-τ slice map, then
-- apply DifferentiableAt.hasDerivAt.comp at interior t ∈ Ioo 0 1.
theorem f_section_chain_rule
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivAt (fun t' => f (H τ t'))
        (deriv f (H τ t) * deriv (H τ) t) t := by
  intro τ hτ t ht
  have hmem_t : t ∈ Set.Icc (0:ℝ) 1 := Set.Ioo_subset_Icc_self ht
  have hmem_τ : τ ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hτ
  have hHVmem : H τ t ∈ V := hHV τ hmem_τ t hmem_t
  have hHτC1 : ContDiffOn ℝ 1 (H τ) (Set.Icc (0:ℝ) 1) := by
    have hcomp : ContDiffOn ℝ 2 (fun t' => H τ t') (Set.Icc (0:ℝ) 1) := by
      have := hH.comp (contDiffOn_const.prodMk contDiffOn_id)
        (fun t' ht' => Set.mk_mem_prod hmem_τ ht')
      simpa using this
    exact hcomp.of_le (by norm_num)
  have hHτDiff : DifferentiableAt ℝ (H τ) t :=
    (hHτC1.differentiableOn one_ne_zero).differentiableAt
      (Icc_mem_nhds ht.1 ht.2)
  have hfDiff : DifferentiableAt ℂ f (H τ t) :=
    hf.differentiableOn.differentiableAt (hV.mem_nhds hHVmem)
  exact hfDiff.hasDerivAt.comp t hHτDiff.hasDerivAt

end Problems.residue_thm
