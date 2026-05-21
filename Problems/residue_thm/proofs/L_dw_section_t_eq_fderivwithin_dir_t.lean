import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- dw_section_t_eq_fderivwithin_dir_t: derivWithin of H τ' section equals
-- joint fderivWithin applied to (0,1) direction, via section embedding (lesson 34)
theorem dw_section_t_eq_fderivwithin_dir_t
    {H : ℝ → ℝ → ℂ}
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (t : ℝ) (ht : t ∈ Set.Ioo (0:ℝ) 1) :
    ∀ τ' ∈ Set.Icc (0:ℝ) 1,
      derivWithin (H τ') (Set.Icc (0:ℝ) 1) t =
        fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t) (0, 1) := by
  intro τ' hτ'
  have ht' : t ∈ Set.Icc (0:ℝ) 1 := Set.Ioo_subset_Icc_self ht
  have hpt : (τ', t) ∈ Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1 := Set.mk_mem_prod hτ' ht'
  have hfderiv : HasFDerivWithinAt (fun p : ℝ × ℝ => H p.1 p.2)
      (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t) :=
    (hH.differentiableOn (by norm_num) _ hpt).hasFDerivWithinAt
  have hsection : HasDerivWithinAt (fun t' : ℝ => (τ', t')) ((0:ℝ), (1:ℝ))
      (Set.Icc (0:ℝ) 1) t :=
    (hasDerivWithinAt_const t _ τ').prodMk (hasDerivWithinAt_id t _)
  have hmaps : Set.MapsTo (fun t' : ℝ => (τ', t')) (Set.Icc (0:ℝ) 1)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    fun t' ht'' => Set.mk_mem_prod hτ' ht''
  exact (hfderiv.comp_hasDerivWithinAt t hsection hmaps).derivWithin
    (uniqueDiffOn_Icc_zero_one t ht')

end Problems.residue_thm
