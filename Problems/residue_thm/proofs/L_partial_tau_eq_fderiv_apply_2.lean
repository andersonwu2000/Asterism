import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- partial_tau_eq_fderiv_apply_2: chain rule via HasFDerivWithinAt.comp_hasDerivWithinAt
-- derivWithin (fun τ' => H τ' t) (Icc 0 1) τ equals fderivWithin applied to (1,0) by
-- composing HasFDerivWithinAt of H with HasDerivWithinAt of the embedding τ' ↦ (τ', t).
-- entry_kind: Builder
theorem partial_tau_eq_fderiv_apply_2
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1,
      derivWithin (fun τ' => H τ' t) (Set.Icc (0:ℝ) 1) τ =
        fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) (1, 0) := by
    intro τ hτ t ht
    have hemb : HasDerivWithinAt (fun τ' => (τ', t)) ((1:ℝ), (0:ℝ))
        (Set.Icc (0:ℝ) 1) τ :=
      (hasDerivWithinAt_id _ _).prodMk (hasDerivWithinAt_const _ _ _)

    have himg : Set.MapsTo (fun τ' => (τ', t)) (Set.Icc (0:ℝ) 1)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
      fun τ' hτ' => ⟨hτ', ht⟩
    have hmem : (τ, t) ∈ Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1 :=
      ⟨Set.Ico_subset_Icc_self hτ, ht⟩
    have hF := (hH.differentiableOn (by norm_num) _ hmem).hasFDerivWithinAt
    have hchain := hF.comp_hasDerivWithinAt τ hemb himg
    have huniq := uniqueDiffOn_Icc_zero_one τ (Set.Ico_subset_Icc_self hτ)
    exact hchain.derivWithin huniq

end Problems.residue_thm
