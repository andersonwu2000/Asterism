import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- h_section_dw_eq_fderiv_apply_zero_one: t-section derivWithin equals joint fderivWithin at (0,1),
-- over the full Icc (not just Ioo interior). Direct slice chain rule via
-- HasFDerivWithinAt.comp_hasDerivWithinAt on embedding t' ↦ (τ, t').
theorem h_section_dw_eq_fderiv_apply_zero_one
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1,
      derivWithin (H τ) (Set.Icc (0:ℝ) 1) t =
        fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) ((0:ℝ), (1:ℝ)) := by
  intro τ hτ t ht
  have hHfd : HasFDerivWithinAt (fun q : ℝ × ℝ => H q.1 q.2)
      (fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) :=
    (hH.differentiableOn (by norm_num) (τ, t) (Set.mk_mem_prod hτ ht)).hasFDerivWithinAt
  have hfund : HasDerivWithinAt (fun t' => (τ, t')) ((0:ℝ), (1:ℝ)) (Set.Icc (0:ℝ) 1) t :=
    (hasDerivWithinAt_const t _ τ).prodMk (hasDerivWithinAt_id t _)
  have hmaps : Set.MapsTo (fun t' => (τ, t'))
      (Set.Icc (0:ℝ) 1) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    fun t' ht' => Set.mk_mem_prod hτ ht'
  have hchain : HasDerivWithinAt (H τ)
      ((fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t)) ((0:ℝ), (1:ℝ)))
      (Set.Icc (0:ℝ) 1) t :=
    hHfd.comp_hasDerivWithinAt t hfund hmaps
  exact hchain.derivWithin (uniqueDiffOn_Icc_zero_one t ht)

end Problems.residue_thm
