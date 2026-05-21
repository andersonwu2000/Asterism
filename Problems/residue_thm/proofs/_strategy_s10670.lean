import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_h_eq_beta_on_right_half
import Problems.residue_thm.proofs.L_right_half_h_contdiffon_wrap
import Problems.residue_thm.proofs.L_subst_h_eq_beta_right_half

namespace Problems.residue_thm

-- Decompose by abstracting `h := the piecewise integral primitive` and showing
-- (1) `h` is C¹ on `Icc 0 1` (wrapper for proved `flat_concat_ftc_smooth`);
-- (2) `h t = β' (2t - 1)` pointwise on `Icc (1/2) 1`
--     (combining left-half FTC eval `α' 1 - α' 0` with right-half eval
--      `β' (2t-1) - β' 0` and `h_match : α' 1 = β' 0` cancels the constant);
-- (3) the abstract substitution `u = 2t - 1` taking
--     `∫_(1/2)^1 Q (h t) * deriv h t = ∫_0^1 Q (β' t) * deriv β' t`
--     for any C¹ `h` agreeing with `β' (2t-1)` on the right half.
theorem s10670
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    (∫ t in ((1/2:ℝ))..1,
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) =
      (∫ t in (0:ℝ)..1, Q (β' t) * deriv β' t)  := by
  have hh_smooth := right_half_h_contdiffon_wrap hα' hβ' h_match hα'_deriv hβ'_deriv
  have hh_eq := h_eq_beta_on_right_half hα' hβ' h_match hα'_deriv hβ'_deriv
  exact subst_h_eq_beta_right_half (Q := Q) hβ' hh_smooth hh_eq

end Problems.residue_thm
