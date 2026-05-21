import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_flat_concat_left_half_piecewise_eval
import Problems.residue_thm.proofs.L_flat_concat_piecewise_integral_split_at_half
import Problems.residue_thm.proofs.L_flat_concat_right_half_piecewise_eval

namespace Problems.residue_thm

-- Split ∫₀ᵗ piecewise = ∫₀^{1/2} + ∫_{1/2}^t, evaluate each via FTC on α' / β',
-- then collapse with `h_match : α' 1 = β' 0` and `ring` over ℂ.
-- Three sub-goals: split-at-half (additivity), left-half FTC (gives α'1 − α'0),
-- right-half FTC parameterised by `t ∈ Icc (1/2) 1` (gives β'(2t−1) − β'0).
theorem s10664
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc ((1:ℝ)/2) 1,
      α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) = β' (2*t - 1)  := by
  intro t ht
  have hA :=
    flat_concat_piecewise_integral_split_at_half hα' hβ' h_match hα'_deriv hβ'_deriv t ht
  have hB :=
    flat_concat_left_half_piecewise_eval hα' hβ' h_match hα'_deriv hβ'_deriv
  have hC :=
    flat_concat_right_half_piecewise_eval hα' hβ' h_match hα'_deriv hβ'_deriv t ht
  rw [hA, hB, hC, h_match]
  ring

end Problems.residue_thm
