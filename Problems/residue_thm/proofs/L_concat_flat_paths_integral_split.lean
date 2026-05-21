-- FTC-of-velocity construction. Define `αβ` as the integral primitive of the
-- piecewise-defined velocity `v(s) := if s ≤ 1/2 then 2·derivWithin α' (Icc 0 1) (2s)
-- else 2·derivWithin β' (Icc 0 1) (2s−1)`. Two flat-endpoint hypotheses make `v`
-- continuous at the join `s = 1/2` (both sides equal `0`); FTC then turns the
-- continuous-velocity primitive into a `ContDiffOn ℝ 1` path. Half-interval
-- representations `αβ = α'(2t)` on `[0, 1/2]` / `αβ = β'(2t−1)` on `[1/2, 1]`
-- collapse the endpoint values, avoidance (using `hα'_avoid` / `hβ'_avoid`),
-- and feed the integral-split sub-goal whose proof now has `hQ_an` in scope
-- for integrability of `Q ∘ αβ · deriv αβ`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10661

namespace Problems.residue_thm

def concat_flat_paths_integral_split := @Problems.residue_thm.s10661

end Problems.residue_thm
