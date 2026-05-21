import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- partial_tau_eq_fderiv_apply: τ-slice derivWithin equals fderivWithin in direction (1,0),
-- proved via the chain rule for HasFDerivWithinAt.comp_hasDerivWithinAt.
theorem partial_tau_eq_fderiv_apply
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
  have hφ : HasDerivWithinAt (fun τ' => (τ', t)) ((1:ℝ), (0:ℝ)) (Set.Icc (0:ℝ) 1) τ :=
    (hasDerivWithinAt_id τ _).prodMk (hasDerivWithinAt_const τ _ t)
  have hDiff : DifferentiableWithinAt ℝ (fun p : ℝ × ℝ => H p.1 p.2)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) :=
    hH.differentiableOn (by norm_num) (τ, t) ⟨Set.Ico_subset_Icc_self hτ, ht⟩
  have hFderiv : HasFDerivWithinAt (fun p : ℝ × ℝ => H p.1 p.2)
      (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) := hDiff.hasFDerivWithinAt
  have hmaps : Set.MapsTo (fun τ' => (τ', t)) (Set.Icc (0:ℝ) 1)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    fun _ hτ' => Set.mk_mem_prod hτ' ht
  have hchain : HasDerivWithinAt (fun τ' => H τ' t)
      (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1)
        (τ, t) (1, 0))
      (Set.Icc (0:ℝ) 1) τ := by
    exact HasFDerivWithinAt.comp_hasDerivWithinAt_of_eq τ hFderiv hφ hmaps rfl
  exact hchain.derivWithin (uniqueDiffOn_Icc_zero_one τ (Set.Ico_subset_Icc_self hτ))

end Problems.residue_thm
