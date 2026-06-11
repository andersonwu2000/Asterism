-- Direct proof (no sub-goals): the identity is definitional bookkeeping.
-- `hp` gives `(extChartAt I x).symm (extChartAt I x p) = p` via `left_inv`; transporting
-- that along the constant-fiber read `q ↦ continuousLinearMapAt ℝ e q (φ q)` (congrArg,
-- since the dependent rewrite is blocked by `q` in the fiber type) reduces `formInCoord`
-- to the trivialization read at `p`; `continuousLinearMapAt_apply_of_mem` turns it into
-- the raw pair read, which is `formCoordChange I k (achart H p) (achart H x) p (φ p)`
-- by `rfl` (`formBundleCore.coordChange = formCoordChange`, `indexAt = achart`).
import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs._strategy_s11689

namespace Problems.Geometry.stokes_mextderiv

def form_in_coord_eq_coord_change := @Problems.Geometry.stokes_mextderiv.s11689

end Problems.Geometry.stokes_mextderiv
