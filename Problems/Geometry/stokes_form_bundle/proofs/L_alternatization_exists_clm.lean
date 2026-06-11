-- Bundle `ContinuousMultilinearMap.alternatization` (Mathlib has it only as `→+`) into a CLM
-- via `LinearMap.mkContinuous`: sub-goal `alternatization_smul` supplies ℝ-homogeneity (additivity
-- is Mathlib's `map_add`), sub-goal `alternatization_norm_le` supplies the operator bound
-- `‖alternatization m‖ ≤ (card ι)! * ‖m‖` (sum of (card ι)! sign-permuted copies of `m`).
-- The witness applies to `m` as `alternatization m` definitionally, so the ∀-clause is `rfl`.
import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_form_bundle.proofs._strategy_s11682

namespace Problems.Geometry.stokes_form_bundle

def alternatization_exists_clm := @Problems.Geometry.stokes_form_bundle.s11682

end Problems.Geometry.stokes_form_bundle
