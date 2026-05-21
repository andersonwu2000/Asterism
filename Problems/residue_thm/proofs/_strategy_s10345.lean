import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_deriv_h_t_section_diff_within_tau
import Problems.residue_thm.proofs.L_f_section_chain_hasderivwithin_tau

namespace Problems.residue_thm

-- Product+chain rule for τ-derivWithin: combine a HasDerivWithinAt chain rule on
-- (τ' ↦ f (H τ' t)) with τ-side DifferentiableWithinAt of (τ' ↦ deriv (H τ') t),
-- then apply `HasDerivWithinAt.mul` and `.derivWithin` over `uniqueDiffOn_Icc_zero_one`.
-- Residue between the .mul output `(c' · d) * b + c · d'` and the goal's
-- `c · b · c' + c · d'` is a pure ring permutation handled by `linear_combination`.
theorem s10345
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      deriv f (H τ t) * deriv (H τ) t
          * derivWithin (fun τ' => H τ' t) (Set.Icc (0:ℝ) 1) τ
        + f (H τ t) * derivWithin (fun τ' => deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ
      = derivWithin (fun τ' => f (H τ' t) * deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ  := by
  intro τ hτ t ht
  have hτIcc : τ ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hτ
  have hA := f_section_chain_hasderivwithin_tau hV hf hH hHV hH0 hH1 τ hτ t ht
  have hB := deriv_h_t_section_diff_within_tau hV hf hH hHV hH0 hH1 τ hτ t ht
  have h := (hA.mul hB.hasDerivWithinAt).derivWithin
              (uniqueDiffOn_Icc_zero_one τ hτIcc)
  linear_combination -h

end Problems.residue_thm
