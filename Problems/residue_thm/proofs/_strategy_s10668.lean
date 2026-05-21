import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_flat_ftc_intintegrable_left_half
import Problems.residue_thm.proofs.L_flat_ftc_intintegrable_right_half

namespace Problems.residue_thm

-- Apply `intervalIntegral.integral_add_adjacent_intervals` at the midpoint `1/2`.
-- The combinator closes the parent (a = ∫_{[0,1]}, b + c = ∫_{[0,1/2]} + ∫_{[1/2,1]})
-- via `.symm`. Sub-goals: `IntervalIntegrable` for the integrand on each half.
theorem s10668
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
      (∫ t in (0:ℝ)..(1/2:ℝ),
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) +
      (∫ t in ((1/2:ℝ))..1,
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t)  := by
  have h1 :=
    flat_ftc_intintegrable_left_half hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  have h2 :=
    flat_ftc_intintegrable_right_half hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  exact (intervalIntegral.integral_add_adjacent_intervals h1 h2).symm

end Problems.residue_thm
