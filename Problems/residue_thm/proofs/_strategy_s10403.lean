import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct: `fderivWithin` of a C² function (one degree lost) is C¹, hence has a Fréchet
-- derivative on the unique-diff product `Icc×Icc`; applying that derivative pointwise at the
-- constant `(1,0)` direction via `HasFDerivWithinAt.clm_apply` (paired with
-- `hasFDerivWithinAt_const`) yields the iterated form, with the `(...).comp 0` summand
-- simped away to leave `.flip (1,0)`.
theorem s10403
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasFDerivWithinAt
        (fun p : ℝ × ℝ => fderivWithin ℝ (fun p' : ℝ × ℝ => H p'.1 p'.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p (1, 0))
        ((fderivWithin ℝ (fderivWithin ℝ (fun p' : ℝ × ℝ => H p'.1 p'.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t)).flip (1, 0))
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t)  := by
  intro τ hτ t ht
  have hUD : UniqueDiffOn ℝ (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    UniqueDiffOn.prod uniqueDiffOn_Icc_zero_one uniqueDiffOn_Icc_zero_one
  have hmem : (τ, t) ∈ Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1 :=
    ⟨Set.Ico_subset_Icc_self hτ, Set.Ioo_subset_Icc_self ht⟩
  have h_fd_C1 : ContDiffOn ℝ 1
      (fun p : ℝ × ℝ => fderivWithin ℝ (fun p' : ℝ × ℝ => H p'.1 p'.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    hH.fderivWithin hUD (by norm_num)
  have hD : HasFDerivWithinAt
      (fun p : ℝ × ℝ => fderivWithin ℝ (fun p' : ℝ × ℝ => H p'.1 p'.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p)
      (fderivWithin ℝ
          (fderivWithin ℝ (fun p' : ℝ × ℝ => H p'.1 p'.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) :=
    (h_fd_C1.differentiableOn (by norm_num) _ hmem).hasFDerivWithinAt
  have hConst : HasFDerivWithinAt (fun _ : ℝ × ℝ => ((1:ℝ), (0:ℝ)))
      (0 : (ℝ × ℝ) →L[ℝ] (ℝ × ℝ))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) :=
    hasFDerivWithinAt_const _ _ _
  have h := hD.clm_apply hConst
  simpa using h

end Problems.residue_thm
