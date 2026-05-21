-- Pick witness `g_a z = h a z - ∑ b ∈ T.erase a, P b z`.
-- Sub-goal 1 (analytic): this candidate is analytic on `Metric.ball a (R a)`
-- (since `h a` is analytic there and every `P b` with `b ≠ a` is analytic on
--  the ball because `b ∉ Metric.ball a (R a)` by separation).
-- Sub-goal 2 (identity): on the punctured ball the candidate equals
-- `f z - ∑ b ∈ T, P b z` — split `T = insert a (T.erase a)` and use
-- `f z = h a z + P a z`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10466

namespace Problems.residue_thm

def local_extension_at_pole_exists := @Problems.residue_thm.s10466

end Problems.residue_thm
