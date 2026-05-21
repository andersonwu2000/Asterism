import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_fderivwithin_joint_contdiff_one
import Problems.residue_thm.proofs.L_f_h_joint_contdiff_one

namespace Problems.residue_thm

-- Split the C¹ product into its two factors and recombine via `ContDiffOn.mul`.
-- (1) `f_h_joint_contdiff_one`: `f ∘ H` is C¹ on `Icc×Icc`.
-- (2) `fderivwithin_joint_contdiff_one`: the within-derivative of `H` evaluated at
--     `(0,1)` is C¹ on `Icc×Icc` (`ContDiffOn.fderivWithin` on the unique-diff
--     product set, then post-composed with the linear evaluation at `(0,1)`).
theorem s10358
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ContDiffOn ℝ 1
      (fun p : ℝ × ℝ =>
        f (H p.1 p.2) *
          fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p ((0:ℝ), (1:ℝ)))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1)  := by
  have h_fH := f_h_joint_contdiff_one hV hf hH hHV hH0 hH1
  have h_dH := fderivwithin_joint_contdiff_one hV hf hH hHV hH0 hH1
  exact h_fH.mul h_dH

end Problems.residue_thm
