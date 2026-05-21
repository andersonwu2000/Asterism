-- Split ∫₀ᵗ piecewise = ∫₀^{1/2} + ∫_{1/2}^t, evaluate each via FTC on α' / β',
-- then collapse with `h_match : α' 1 = β' 0` and `ring` over ℂ.
-- Three sub-goals: split-at-half (additivity), left-half FTC (gives α'1 − α'0),
-- right-half FTC parameterised by `t ∈ Icc (1/2) 1` (gives β'(2t−1) − β'0).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10664

namespace Problems.residue_thm

def flat_concat_ftc_right_half := @Problems.residue_thm.s10664

end Problems.residue_thm
