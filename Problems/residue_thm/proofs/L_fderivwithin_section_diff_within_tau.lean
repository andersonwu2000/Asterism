-- Chain rule via the slice map `τ' ↦ (τ', t)`: pre-compose with the joint
-- DifferentiableWithinAt of `p ↦ fderivWithin ℝ G (Icc×Icc) p (0,1)` at the
-- prod point `(τ, t)` (sub-goal `fderiv_apply_diff_within_at_prod`, available
-- from the proved sibling `fderivwithin_joint_contdiff_one`'s `ContDiffOn ℝ 1`),
-- with the slice `(τ' ↦ (τ', t))` being differentiable and `MapsTo`-mapping
-- `Icc 0 1` into `Icc×Icc` thanks to `t ∈ Ioo ⊂ Icc`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10361

namespace Problems.residue_thm

def fderivwithin_section_diff_within_tau := @Problems.residue_thm.s10361

end Problems.residue_thm
