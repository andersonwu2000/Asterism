-- Local-radius substitution: near `z₁`, both `z ↦ (dist z z₀ + R)/2` and the constant
-- `(dist z₁ z₀ + R)/2` are valid radii for the kernel `w ↦ f w / (w - z)`, so by
-- annular radius-independence the two circle integrals agree pointwise on a nbhd of z₁.
-- Sub-goal `local_radii_nhd_event` (Builder, metric/topology only): exhibits the nbhd on which
--   `z ∈ ball z₀ R` and `dist z z₀ < (dist z₁ z₀ + R)/2` both hold — pure continuity argument.
-- Sub-goal `kernel_int_local_radii_eq` (Builder, direct sibling call): pointwise radius
--   equality of `∮ w in C(z₀,·), f w / (w - z)` between the two radii on the witness nbhd,
--   bundled as a clean specialization of the proved `cauchy_kernel_circle_int_radius_indep`.
-- Combinator: introduce `z₁`, take the nbhd event, rewrite the per-z integrals via the
-- equality lemma, multiply by `(2πi)⁻¹` via `congr_arg`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10425

namespace Problems.residue_thm

def outer_g_local_radius_equality := @Problems.residue_thm.s10425

end Problems.residue_thm
