-- Decompose `∫₀ᵗ v(s) ds = α'(2t) - α'(0)` (then add α'(0)) into:
-- (1) the if-branch collapses to `2·derivWithin α' (2s)` on the prefix `[0,t] ⊆ [0,1/2]`;
-- (2) FTC + linear substitution gives `∫₀ᵗ 2·derivWithin α' (2s) ds = α'(2t) - α'(0)`.
-- Combine by rewriting LHS → simplified integral → `α'(2t) - α'(0)`, then `α'(0) + …` cancels.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10663

namespace Problems.residue_thm

def flat_concat_ftc_left_half := @Problems.residue_thm.s10663

end Problems.residue_thm
