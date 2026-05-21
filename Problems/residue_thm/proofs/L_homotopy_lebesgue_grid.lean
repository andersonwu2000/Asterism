-- Lebesgue-grid construction for continuous H on the unit square into open U.
-- (1) `homotopy_uniform_thickening` (compact-image thickening): uniform δ>0 with
--     `ball (H τ t) δ ⊆ U` for every (τ,t) in the unit square.
-- (2) `homotopy_modulus_grid` (Heine-Cantor + Archimedean): given ε>0, pick N so
--     each N×N cell has diameter under H's modulus for ε.
-- Combine: take ε := δ. Then c i j := H (i/N) (j/N) and r i j := δ; the ball-in-U
-- condition uses (1) at grid points, and pointwise membership uses (2) with ε = δ.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10582

namespace Problems.residue_thm

def homotopy_lebesgue_grid := @Problems.residue_thm.s10582

end Problems.residue_thm
