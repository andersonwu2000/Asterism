-- Schwarz mixed-partial bridge. Decompose via three rewrites:
-- (A) Symmetry of the iterated `fderivWithin` (Schwarz) swaps the directions (0,1)/(1,0).
-- (B) The (1,0)-direction iterated fderivWithin at (τ,t) equals the τ-section
--     `derivWithin (fun τ' => fderivWithin H U (τ',t) (0,1)) (Icc 0 1) τ` (lesson-34
--     pattern, applied on the τ-side).
-- (C) The inner section `fun τ' => fderivWithin H U (τ',t) (0,1)` agrees on `Icc 0 1`
--     with `fun τ' => deriv (H τ') t` (lesson-34 pattern in the t-direction; uses
--     `t ∈ Ioo 0 1` so `Icc 0 1 ∈ 𝓝 t`), giving equal `derivWithin`s.
-- Combine via three `.trans`'s.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10366

namespace Problems.residue_thm

def schwarz_mixed_partial_bridge := @Problems.residue_thm.s10366

end Problems.residue_thm
