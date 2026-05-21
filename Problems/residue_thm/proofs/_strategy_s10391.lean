import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_g_joint_diff_within_icc

namespace Problems.residue_thm

-- Section chain rule: differentiate the τ'-slice `τ' ↦ g(τ', t)` of the joint
-- cleaned product `g(p) = f(H p.1 p.2) * fderivWithin H_joint (Icc×Icc) p (0,1)`
-- by composing the joint `HasFDerivWithinAt` at `(τ, t)` with the section embedding
-- `τ' ↦ (τ', t)` (whose derivative is `(1, 0)`), then closing via
-- `HasDerivWithinAt.derivWithin` over `uniqueDiffOn_Icc_zero_one`. Sole sub-goal
-- `g_joint_diff_within_icc` supplies `DifferentiableWithinAt ℝ g (Icc×Icc) (τ, t)`
-- — derivable from `clean_g_joint_contdiff_one`'s `ContDiffOn ℝ 1`.
theorem s10391
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1,
      derivWithin (fun τ' =>
          f (H τ' t) * fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t) ((0:ℝ), (1:ℝ)))
          (Set.Icc (0:ℝ) 1) τ =
        fderivWithin ℝ
          (fun p : ℝ × ℝ =>
            f (H p.1 p.2) *
              fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
                (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p ((0:ℝ), (1:ℝ)))
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) ((1:ℝ), (0:ℝ))  := by
  intro τ hτ t ht
  have hτIcc : τ ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hτ
  have hmem : (τ, t) ∈ Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1 := Set.mk_mem_prod hτIcc ht
  have hg : DifferentiableWithinAt ℝ
      (fun p : ℝ × ℝ =>
        f (H p.1 p.2) *
          fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p ((0:ℝ), (1:ℝ)))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) :=
    g_joint_diff_within_icc hV hf hH hHV hH0 hH1 τ hτ t ht
  have hslice : HasDerivWithinAt (fun τ' : ℝ => (τ', t)) ((1:ℝ), (0:ℝ))
      (Set.Icc (0:ℝ) 1) τ :=
    (hasDerivWithinAt_id τ _).prodMk (hasDerivWithinAt_const _ _ t)
  have hmaps : Set.MapsTo (fun τ' : ℝ => (τ', t)) (Set.Icc (0:ℝ) 1)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) := fun τ' hτ' => Set.mk_mem_prod hτ' ht
  have hcomp := hg.hasFDerivWithinAt.comp_hasDerivWithinAt τ hslice hmaps
  exact hcomp.derivWithin (uniqueDiffOn_Icc_zero_one τ hτIcc)

end Problems.residue_thm
