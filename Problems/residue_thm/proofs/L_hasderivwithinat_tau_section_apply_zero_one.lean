import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- hasderivwithinat_tau_section_apply_zero_one: τ-section derivative of CLM-applied fderivWithin
-- Chain rule: τ' ↦ (τ',t) section of G = fderivWithin F (Icc×Icc), then evaluate CLM at (0,1)
theorem hasderivwithinat_tau_section_apply_zero_one
    {H : ℝ → ℝ → ℂ}
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1)) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivWithinAt
        (fun τ' => (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t)) ((0:ℝ), (1:ℝ)))
        ((fderivWithin ℝ (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
                (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t)) ((1:ℝ), (0:ℝ)) ((0:ℝ), (1:ℝ)))
        (Set.Icc (0:ℝ) 1) τ := by
  intro τ hτ t ht
  set F := fun p : ℝ × ℝ => H p.1 p.2
  set S := Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1
  set G := fderivWithin ℝ F S
  have hτS : τ ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hτ
  have htS : t ∈ Set.Icc (0:ℝ) 1 := Set.Ioo_subset_Icc_self ht
  -- ContDiffOn ℝ 2 F S implies G = fderivWithin F S is DifferentiableOn
  have hGdiff : DifferentiableWithinAt ℝ G S (τ, t) := by
    have hG1 : ContDiffOn ℝ 1 G S :=
      hH.fderivWithin (UniqueDiffOn.prod uniqueDiffOn_Icc_zero_one uniqueDiffOn_Icc_zero_one)
        (by norm_num)
    exact hG1.differentiableOn (by norm_num) (τ, t) (Set.mk_mem_prod hτS htS)
  -- HasFDerivWithinAt G at (τ, t)
  have hGfd : HasFDerivWithinAt G (fderivWithin ℝ G S (τ, t)) S (τ, t) :=
    hGdiff.hasFDerivWithinAt
  -- τ-section embedding τ' ↦ (τ', t) has derivative (1, 0)
  have hsec : HasDerivWithinAt (fun τ' => (τ', t)) ((1:ℝ), (0:ℝ))
      (Set.Icc (0:ℝ) 1) τ :=
    (hasDerivWithinAt_id τ _).prodMk (hasDerivWithinAt_const τ _ t)
  -- MapsTo τ-section
  have hmaps : Set.MapsTo (fun τ' => (τ', t)) (Set.Icc (0:ℝ) 1) S :=
    fun τ' hτ' => Set.mk_mem_prod hτ' htS
  -- Chain rule: HasDerivWithinAt of G ∘ section
  have hcomp : HasDerivWithinAt (fun τ' => G (τ', t))
      (fderivWithin ℝ G S (τ, t) ((1:ℝ), (0:ℝ)))
      (Set.Icc (0:ℝ) 1) τ :=
    hGfd.comp_hasDerivWithinAt τ hsec hmaps
  -- Apply CLM at (0, 1): use clm_apply with constant derivative
  have hfinal := hcomp.clm_apply (hasDerivWithinAt_const τ (Set.Icc (0:ℝ) 1) ((0:ℝ), (1:ℝ)))
  simp only [map_zero, add_zero] at hfinal
  exact hfinal

end Problems.residue_thm
