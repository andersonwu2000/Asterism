import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_fderivwithin_apply10_hasfderivwithinat

namespace Problems.residue_thm

-- Section chain rule for the partial in (1,0) direction: decompose into
-- `HasFDerivWithinAt.comp_hasDerivWithinAt` with the section embedding
-- `t' ↦ (τ, t')`. Sub-goal `fderivwithin_apply10_hasfderivwithinat` supplies
-- the joint Fréchet differentiability of `p ↦ fderivWithin H' s p (1,0)` at
-- `(τ, t)` with derivative `(fderivWithin (fderivWithin H' s) s (τ,t)).flip (1,0)`;
-- the section embedding has derivative `(0,1)` and the inner apply collapses
-- via `ContinuousLinearMap.flip_apply` to the goal's iterated form.
theorem s10396
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivWithinAt
        (fun t' => (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t')) (1, 0))
        ((fderivWithin ℝ (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t)) (0, 1) (1, 0))
        (Set.Icc 0 1) t  := by
  intro τ hτ t ht
  have hτIcc : τ ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hτ
  have h_section : HasDerivWithinAt (fun t' : ℝ => (τ, t')) ((0:ℝ), (1:ℝ))
      (Set.Icc (0:ℝ) 1) t :=
    (hasDerivWithinAt_const t _ τ).prodMk (hasDerivWithinAt_id t _)
  have h_mapsto : Set.MapsTo (fun t' : ℝ => (τ, t'))
      (Set.Icc (0:ℝ) 1) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    fun t' ht' => Set.mk_mem_prod hτIcc ht'
  have h_K := fderivwithin_apply10_hasfderivwithinat
      hV hf hH hHV hH0 hH1 τ hτ t ht
  have hres := h_K.comp_hasDerivWithinAt t h_section h_mapsto
  simpa [ContinuousLinearMap.flip_apply, Function.comp] using hres

end Problems.residue_thm
