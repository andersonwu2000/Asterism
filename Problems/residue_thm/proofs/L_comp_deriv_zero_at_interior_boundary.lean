-- Decomposition (Lipschitz + zero-derivative interior strategy):
-- (a) `phi_deriv_zero_alias`: deriv φ t = 0 — sibling-style alias of
--     `phi_deriv_zero_at_interior_boundary` (monotonicity + boundary image).
-- (b) `gamma_lipschitz_on_unit_icc`: γ is Lipschitz on Icc 0 1 (C¹ on a compact).
-- (c) `lipschitz_comp_has_deriv_zero`: abstract — if f is Lipschitz on s,
--     g eventually lives in s near t, and `HasDerivAt g 0 t`, then
--     `HasDerivAt (f ∘ g) 0 t` (no need for f to be differentiable at g t).
-- Combine: build `HasDerivAt (γ ∘ φ) 0 t`, then take `.deriv`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10646

namespace Problems.residue_thm

def comp_deriv_zero_at_interior_boundary := @Problems.residue_thm.s10646

end Problems.residue_thm
