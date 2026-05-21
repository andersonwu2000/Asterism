import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Slice chain rule: t-section derivWithin equals joint fderivWithin applied to (0,1).
-- Direct closure via HasFDerivWithinAt.comp_hasDerivWithinAt on the embedding
-- t' ↦ (τ', t'); Ioo ⊆ Icc lifts t ∈ Ioo into the Icc-domain of `hH`.
theorem s10367
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ' ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      derivWithin (H τ') (Set.Icc (0:ℝ) 1) t =
        fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t) (0, 1)  := by
  intro τ' hτ' t ht
  have ht_icc : t ∈ Set.Icc (0:ℝ) 1 := Set.Ioo_subset_Icc_self ht
  have hHfd : HasFDerivWithinAt (fun q : ℝ × ℝ => H q.1 q.2)
      (fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t) :=
    (hH.differentiableOn (by norm_num) (τ', t)
      (Set.mk_mem_prod hτ' ht_icc)).hasFDerivWithinAt
  have hfund : HasDerivWithinAt (fun t' => (τ', t')) ((0:ℝ), (1:ℝ))
      (Set.Icc (0:ℝ) 1) t :=
    (hasDerivWithinAt_const t _ τ').prodMk (hasDerivWithinAt_id t _)
  have hmaps : Set.MapsTo (fun t' => (τ', t'))
      (Set.Icc (0:ℝ) 1) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    fun t' ht' => Set.mk_mem_prod hτ' ht'
  have hchain : HasDerivWithinAt (H τ')
      ((fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t)) ((0:ℝ), (1:ℝ)))
      (Set.Icc (0:ℝ) 1) t :=
    hHfd.comp_hasDerivWithinAt t hfund hmaps
  exact hchain.derivWithin (uniqueDiffOn_Icc_zero_one t ht_icc)

end Problems.residue_thm
