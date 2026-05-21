import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_flat_left_h_contdiff_wrap
import Problems.residue_thm.proofs.L_flat_left_h_eq_alpha_wrap
import Problems.residue_thm.proofs.L_flat_left_int_subst_alpha_wrap

namespace Problems.residue_thm

-- Identify the LHS piecewise-FTC primitive as `α'(2·)` on the left half
-- via the proved sibling `flat_concat_ftc_left_half` (wrapped); change
-- variables `u = 2t` via the abstract substitution lemma matching the
-- open sibling `int_left_half_h_eq_alpha` (wrapped); smoothness comes
-- from `flat_concat_ftc_smooth` (wrapped). Closer is `exact` after `set`.
theorem s10669
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
    (∫ t in (0:ℝ)..(1/2:ℝ),
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) =
      (∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t)  := by
  set h : ℝ → ℂ := fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
            (if s ≤ (1:ℝ)/2
              then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
              else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) with hh_def
  have h_smooth : ContDiffOn ℝ 1 h (Set.Icc 0 1) :=
    flat_left_h_contdiff_wrap hQ_an hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  have h_eq : ∀ t ∈ Set.Icc (0:ℝ) (1/2), h t = α' (2*t) :=
    flat_left_h_eq_alpha_wrap hQ_an hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  exact flat_left_int_subst_alpha_wrap (Q := Q) hQ_an hα' hα'_avoid hβ' hβ'_avoid
    h_match hα'_deriv hβ'_deriv h_smooth h_eq



end Problems.residue_thm
