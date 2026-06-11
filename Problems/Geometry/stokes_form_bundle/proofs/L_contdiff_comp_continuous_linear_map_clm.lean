-- Factor the alternating pullback `g ↦ compContinuousLinearMapCLM g` through its multilinear
-- analogue: Mathlib's `compContinuousLinearMapContinuousMultilinear` is a continuous multilinear
-- map, hence `C^n`; precomposing with the diagonal `g ↦ (fun _ : ι ↦ g)` gives `h_diag`.
-- A bundled alternatization CLM `A` (sub-goal `alternatization_exists_clm`) is, after scaling by
-- `1/(card ι)!`, a continuous-linear left inverse of the inclusion of alternating into multilinear
-- maps, so the target equals a fixed CLM applied to the `C^n` multilinear-side map (`h_key`,
-- sub-goal `comp_clm_eq_inv_factorial_smul`); `clm_comp`/`const_smul` then close the goal.
import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_form_bundle.proofs._strategy_s11679

namespace Problems.Geometry.stokes_form_bundle

def contdiff_comp_continuous_linear_map_clm := @Problems.Geometry.stokes_form_bundle.s11679

end Problems.Geometry.stokes_form_bundle
