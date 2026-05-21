import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_contdiffon_fderiv_apply_partial_t
import Problems.residue_thm.proofs.L_eq_partial_t_to_fderiv_apply

namespace Problems.residue_thm

-- Equate `deriv (H p.1) p.2` on `Ioo×Ioo` to evaluation of the joint
-- Fréchet derivative `fderiv (H ·.1 ·.2) p (0,1)`, then transport
-- ContDiffOn ℝ 1 of the fderiv-evaluation form across the equality.
-- (a) `eq_partial_t_to_fderiv_apply` is a pointwise differential-calculus
-- identity (Builder).  (b) `contdiffon_fderiv_apply_partial_t` follows from
-- `ContDiffOn.fderiv_of_isOpen` (drops one order on an open set) composed
-- with the continuous-linear evaluation map at `(0,1)` (Backward).
theorem s10348
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ContDiffOn ℝ 1 (fun p : ℝ × ℝ => deriv (H p.1) p.2)
      (Set.Ioo (0:ℝ) 1 ×ˢ Set.Ioo (0:ℝ) 1)  := by
  have h_eq := eq_partial_t_to_fderiv_apply hV hf hH hHV hH0 hH1
  have h_cd := contdiffon_fderiv_apply_partial_t hV hf hH hHV hH0 hH1
  exact h_cd.congr h_eq



end Problems.residue_thm
