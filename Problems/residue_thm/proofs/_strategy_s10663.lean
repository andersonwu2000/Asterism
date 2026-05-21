import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_concat_velocity_if_eq_left_on_prefix
import Problems.residue_thm.proofs.L_integral_two_deriv_within_double_eq_diff

namespace Problems.residue_thm

-- Decompose `∫₀ᵗ v(s) ds = α'(2t) - α'(0)` (then add α'(0)) into:
-- (1) the if-branch collapses to `2·derivWithin α' (2s)` on the prefix `[0,t] ⊆ [0,1/2]`;
-- (2) FTC + linear substitution gives `∫₀ᵗ 2·derivWithin α' (2s) ds = α'(2t) - α'(0)`.
-- Combine by rewriting LHS → simplified integral → `α'(2t) - α'(0)`, then `α'(0) + …` cancels.
theorem s10663
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc (0:ℝ) (1/2),
      α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) = α' (2*t)  := by
  intro t ht
  have h_int_simp := concat_velocity_if_eq_left_on_prefix (α' := α') (β' := β') ht
  have h_ftc := integral_two_deriv_within_double_eq_diff hα' ht
  rw [h_int_simp, h_ftc]; ring

end Problems.residue_thm
