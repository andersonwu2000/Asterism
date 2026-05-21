import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_flat_concat_ftc_integral_split
import Problems.residue_thm.proofs.L_flat_concat_ftc_left_half
import Problems.residue_thm.proofs.L_flat_concat_ftc_right_half
import Problems.residue_thm.proofs.L_flat_concat_ftc_smooth

namespace Problems.residue_thm

-- FTC-of-velocity construction. Define `αβ` as the integral primitive of the
-- piecewise-defined velocity `v(s) := if s ≤ 1/2 then 2·derivWithin α' (Icc 0 1) (2s)
-- else 2·derivWithin β' (Icc 0 1) (2s−1)`. Two flat-endpoint hypotheses make `v`
-- continuous at the join `s = 1/2` (both sides equal `0`); FTC then turns the
-- continuous-velocity primitive into a `ContDiffOn ℝ 1` path. Half-interval
-- representations `αβ = α'(2t)` on `[0, 1/2]` / `αβ = β'(2t−1)` on `[1/2, 1]`
-- collapse the endpoint values, avoidance (using `hα'_avoid` / `hβ'_avoid`),
-- and feed the integral-split sub-goal whose proof now has `hQ_an` in scope
-- for integrability of `Q ∘ αβ · deriv αβ`.
theorem s10661
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
    ∃ αβ : ℝ → ℂ,
      ContDiffOn ℝ 1 αβ (Set.Icc 0 1) ∧
      αβ 0 = α' 0 ∧
      αβ 1 = β' 1 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, αβ t ≠ a) ∧
      (∫ t in (0 : ℝ)..1, Q (αβ t) * deriv αβ t) =
        (∫ t in (0 : ℝ)..1, Q (α' t) * deriv α' t) +
        (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t)  := by
  have h_smooth :
      ContDiffOn ℝ 1
        (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        (Set.Icc 0 1) :=
    flat_concat_ftc_smooth hα' hβ' h_match hα'_deriv hβ'_deriv
  have h_left :
      ∀ t ∈ Set.Icc (0:ℝ) (1/2),
        α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) = α' (2*t) :=
    flat_concat_ftc_left_half hα' hβ' h_match hα'_deriv hβ'_deriv
  have h_right :
      ∀ t ∈ Set.Icc ((1:ℝ)/2) 1,
        α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) = β' (2*t - 1) :=
    flat_concat_ftc_right_half hα' hβ' h_match hα'_deriv hβ'_deriv
  have h_split :
      (∫ t in (0:ℝ)..1, Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
        deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) =
        (∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t) +
        (∫ t in (0:ℝ)..1, Q (β' t) * deriv β' t) :=
    flat_concat_ftc_integral_split hQ_an hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  refine ⟨fun t => α' 0 + ∫ s in (0:ℝ)..t,
            (if s ≤ (1:ℝ)/2
              then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
              else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)),
          h_smooth, ?_, ?_, ?_, h_split⟩
  · -- αβ 0 = α' 0 : integrate over [0,0] yields 0; α' 0 + 0 = α' 0.
    simp
  · -- αβ 1 = β' 1 : use h_right at t = 1.
    have h := h_right 1 ⟨by norm_num, le_refl 1⟩
    show α' 0 + _ = β' 1
    rw [h]; norm_num
  · -- avoidance: case-split on t ≤ 1/2 and substitute the half-rep.
    intro t ht
    show α' 0 + _ ≠ a
    rcases le_or_gt t ((1:ℝ)/2) with htL | htR
    · rw [h_left t ⟨ht.1, htL⟩]
      exact hα'_avoid (2*t) ⟨by linarith [ht.1], by linarith⟩
    · rw [h_right t ⟨le_of_lt htR, ht.2⟩]
      exact hβ'_avoid (2*t - 1) ⟨by linarith, by linarith [ht.2]⟩

end Problems.residue_thm
