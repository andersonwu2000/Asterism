-- Pick a fixed inner radius `R/2`, rewrite `P z` via `hP` for `z` far from `z₀`
-- (eventually in `cocompact ℂ`), then show the resulting parameter integral
-- tends to 0 as `z → ∞` and transport via `Tendsto.congr'`.
-- Sub-goal 1 drops `f`-analyticity and the cocompact/integral asymptotics.
-- Sub-goal 2 drops `P` and the pointwise integral identity.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10414

namespace Problems.residue_thm

def inner_part_value_implies_tendsto_zero := @Problems.residue_thm.s10414

end Problems.residue_thm
