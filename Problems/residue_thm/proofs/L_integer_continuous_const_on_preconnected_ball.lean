-- Locally-constant principle for integer-valued continuous maps on a connected ball.
-- The ball `Metric.ball z r` in ℂ is preconnected (it is convex). Combined with
-- `ContinuousOn n` (where ℤ carries the discrete topology), `IsPreconnected.constant`
-- forces `n w = n z` for every `w` in the ball.
-- (A) `n_continuous_on_ball_from_f` (Builder): the integer label is continuous on
--     the ball because `(n w : ℂ) = f w / (2πi)` on the ball and `Int.cast : ℤ → ℂ`
--     is a topological embedding, so continuity of `f` lifts back to continuity of `n`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10613

namespace Problems.residue_thm

def integer_continuous_const_on_preconnected_ball := @Problems.residue_thm.s10613

end Problems.residue_thm
