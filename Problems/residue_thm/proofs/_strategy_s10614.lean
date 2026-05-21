import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_int_concat_split_at_half_fresh
import Problems.residue_thm.proofs.L_int_split_left_piece_via_chain_rule
import Problems.residue_thm.proofs.L_int_split_right_piece_via_chain_rule

namespace Problems.residue_thm

-- Split the integral over αβ at the midpoint t = 1/2; on each half use the
-- explicit piecewise form (αβ t = α'(2t) on [0,1/2], αβ t = β'(2t-1) on [1/2,1])
-- together with chain-rule change-of-variables u = 2t / u = 2t-1 to identify
-- each half with the corresponding ∫₀..1 over α' / β'.
theorem s10614
    {Q : ℂ → ℂ} {α' β' αβ : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hαβ : ContDiffOn ℝ 1 αβ (Set.Icc 0 1))
    (hαβ_left : ∀ t ∈ Set.Icc (0 : ℝ) (1/2), αβ t = α' (2*t))
    (hαβ_right : ∀ t ∈ Set.Icc (1/2 : ℝ) 1, αβ t = β' (2*t - 1)) :
    (∫ t in (0 : ℝ)..1, Q (αβ t) * deriv αβ t) =
      (∫ t in (0 : ℝ)..1, Q (α' t) * deriv α' t) +
      (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t)  := by
  have h_left := int_split_left_piece_via_chain_rule (Q := Q) hα' hαβ hαβ_left
  have h_right := int_split_right_piece_via_chain_rule (Q := Q) hβ' hαβ hαβ_right
  have h_split := int_concat_split_at_half_fresh (Q := Q) hαβ
  rw [h_split, h_left, h_right]
end Problems.residue_thm
