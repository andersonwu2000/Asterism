import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem int_split_left_piece_via_chain_rule
    {Q : ℂ → ℂ} {α' αβ : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hαβ : ContDiffOn ℝ 1 αβ (Set.Icc 0 1))
    (hαβ_left : ∀ t ∈ Set.Icc (0 : ℝ) (1/2), αβ t = α' (2*t)) :
    (∫ t in (0 : ℝ)..(1/2), Q (αβ t) * deriv αβ t) =
      (∫ t in (0 : ℝ)..1, Q (α' t) * deriv α' t) := by sorry

end Problems.residue_thm
