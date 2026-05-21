-- Decompose via Heine-Cantor + interval-partition: (A) γ on the compact Icc 0 1 is uniformly
-- continuous so some η > 0 satisfies |s - t| < η ⇒ dist (γ s) (γ t) < δ; (B) the unit interval
-- admits a partition with mesh < η. Combining: for s ∈ [t i, t (i+1)] ⊆ [0,1], |s - t i| < η so
-- the per-segment MapsTo into Metric.ball (γ (t i)) δ follows pointwise.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10500

namespace Problems.residue_thm

def partition_subdivides_path_in_ball := @Problems.residue_thm.s10500

end Problems.residue_thm
