import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_flat_ftc_int_additivity_at_half
import Problems.residue_thm.proofs.L_flat_ftc_left_half_int_eq
import Problems.residue_thm.proofs.L_flat_ftc_right_half_int_eq

namespace Problems.residue_thm

-- Split the LHS integral at `t = 1/2` (additivity), then identify each half
-- with the corresponding α'/β' integral via the inverse substitution
-- `u = 2t` (resp. `u = 2t - 1`) which sends γ to α' (resp. β').
-- Sub-goals: integrability/additivity at the midpoint and the two half-integral
-- substitutions are each smaller than the full statement; the closer is `rw`.
theorem s10662
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
    (∫ t in (0:ℝ)..1,
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) =
        (∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t) +
        (∫ t in (0:ℝ)..1, Q (β' t) * deriv β' t)  := by
  have h_add :=
    flat_ftc_int_additivity_at_half hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  have h_left :=
    flat_ftc_left_half_int_eq hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  have h_right :=
    flat_ftc_right_half_int_eq hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  rw [h_add, h_left, h_right]

end Problems.residue_thm
