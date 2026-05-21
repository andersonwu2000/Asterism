-- Decomposition (boundary case φ t ∈ {0,1} at interior t ∈ Ioo 0 1):
-- (a) `phi_deriv_zero_at_interior_boundary`: monotonicity + range force φ to be
--     locally constant on a one-sided neighborhood of t, then C¹-continuity of
--     `deriv φ` (no values at t = 0 or t = 1 needed) gives `deriv φ t = 0`.
-- (b) `comp_deriv_zero_at_interior_boundary`: γ is Lipschitz on Icc 0 1 (C¹ on
--     a compact), so the difference-quotient of `γ ∘ φ` at t is bounded by L
--     times that of φ, which vanishes — giving `deriv (γ ∘ φ) t = 0`.
-- Combine via 0 = 0 • _.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10642

namespace Problems.residue_thm

def chain_rule_at_boundary_image := @Problems.residue_thm.s10642

end Problems.residue_thm
