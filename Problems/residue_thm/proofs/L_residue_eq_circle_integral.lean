-- Decompose by isolating the contour-integral bridge from the residue unfold.
-- One sub-goal: equality of circle integrals at two radii valid for two
-- possibly-different analytic radii — Builder chains the sibling lemma twice
-- via a small auxiliary radius ρ ≤ min r (Classical.choose hex / 2).
-- The combinator builds the existence proof from `hf`, unfolds `Complex.residue`
-- via `dif_pos hex`, peels the `(1/(2πi)) *` factor, and applies the bridge with
-- the analyticity provided by `Classical.choose_spec hex` on one side and `hf` on
-- the other.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10299

namespace Problems.residue_thm

def residue_eq_circle_integral := @Problems.residue_thm.s10299

end Problems.residue_thm
