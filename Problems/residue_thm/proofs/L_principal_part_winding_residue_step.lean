-- Reduce the residue integral identity to two independent pieces:
--   (A) winding_integral_formula (Builder leaf): ∫₀¹ γ'(t)/(γ(t) - a) dt = 2πi · winding γ a
--       — direct from the windingNumber definition and `exists_winding_integer`.
--   (B) path_int_eq_residue_times_winding_int (Backward): the substantive residue identity
--       ∫₀¹ P(γt)·γ'(t) dt = residue P a · ∫₀¹ γ'(t)/(γt - a) dt — decouples residue from
--       winding so the proof can build a primitive of `P(z) - residue P a / (z - a)` on
--       ℂ \ {a} (zero residue ⇒ exact on the punctured plane) without re-doing the dead
--       Fubini/Cauchy-repr routes.
-- Combinator: rewrite via (B) then (A), then ring to commute the factors.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10474

namespace Problems.residue_thm

def principal_part_winding_residue_step := @Problems.residue_thm.s10474

end Problems.residue_thm
