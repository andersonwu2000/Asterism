-- Heine-Cantor modulus + Archimedean uniform mesh: (A) γ on compact Icc 0 1 yields
-- η > 0 with |s - t| < η ⇒ dist (γ s) (γ t) < δ; (B) [0,1] admits a partition with
-- mesh < η. For s ∈ [t i, t (i+1)] ⊆ [0,1], |s - t i| < η so each subarc maps into
-- Metric.ball (γ (t i)) δ pointwise.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10503

namespace Problems.residue_thm

def partition_subdivides_path_in_ball_2 := @Problems.residue_thm.s10503

end Problems.residue_thm
