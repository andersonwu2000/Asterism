-- Subtract the simple-pole residue piece `r/(z-a)` (r := residue P a) from `P` to land in
-- a zero-residue principal-part regime whose closed-path integral vanishes; then split the
-- subtraction back out by integral linearity to recover the target identity.
--   * residue_subtracted_path_int_zero (Backward): ∫₀¹ (P(γt) - r/(γt-a)) γ'(t) dt = 0
--     — Q := P - r/(·-a) is analytic on ℂ\{a}, decays at ∞, residue 0 at `a`, so it admits
--       a primitive on ℂ\{a} and the closed-loop integral collapses.
--   * path_int_split_residue_term (Builder): the integrand-subtraction split — pure interval-
--     integral linearity using `intervalIntegral.integral_sub` + `intervalIntegral.integral_const_mul`
--     once both summands are interval-integrable (P∘γ·γ' continuous; (γ'-)/(γ-a) continuous via h_avoid).
-- Combinator: hA gives the residue-subtracted integral = 0; hB rewrites it as A - r·B;
-- chaining `rw [← hB]; exact hA` yields A - r·B = 0, then `sub_eq_zero.mp` flips to A = r·B.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10476

namespace Problems.residue_thm

def path_int_eq_residue_times_winding_int := @Problems.residue_thm.s10476

end Problems.residue_thm
