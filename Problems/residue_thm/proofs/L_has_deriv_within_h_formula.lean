-- Product-rule decomposition with `derivWithin γ (Icc 0 1) s` as the intermediate
-- derivative value for both factors, avoiding the dead-strategy s10307 issue where
-- `deriv γ 0` is junk (since `Icc 0 1 ∉ nhds 0`, `DifferentiableAt ℝ γ 0` is not
-- implied by `ContDiffOn ℝ 1 γ (Icc 0 1)`); then a single algebraic equality
-- (`value_dw_eq_target`, both sides = 0 since `γ s - a ≠ 0`) transports the
-- product-rule output to the parent's `deriv γ s` shape.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10311

namespace Problems.residue_thm

def has_deriv_within_h_formula := @Problems.residue_thm.s10311

end Problems.residue_thm
