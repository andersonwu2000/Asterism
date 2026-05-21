import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem int_split_right_piece_via_chain_rule
    {Q : ℂ → ℂ} {β' αβ : ℝ → ℂ}
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hαβ : ContDiffOn ℝ 1 αβ (Set.Icc 0 1))
    (hαβ_right : ∀ t ∈ Set.Icc (1/2 : ℝ) 1, αβ t = β' (2*t - 1)) :
    (∫ t in ((1/2) : ℝ)..1, Q (αβ t) * deriv αβ t) =
      (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t) := by sorry

end Problems.residue_thm
