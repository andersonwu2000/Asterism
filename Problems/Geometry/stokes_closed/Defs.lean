/-
  Defs.lean — vocabulary for the closed-manifold Stokes corollary `∫_M dφ = 0`.
  Pulls the same manifold / differential-form tower the statement reads:
    * `DiffForm`            (Problems.Geometry.stokes_form_bundle)
    * `mextDeriv`           (Problems.Geometry.stokes_dd_zero)
    * `OrientedManifold`, `DiffForm.integral` (Problems.Geometry.stokes_integral)
    * `Bdry`                (Problems.Geometry.stokes_bdry_compact)
  No new definitions — this problem only states a corollary of the proved Stokes theorem.
-/
import Mathlib
import Problems.Geometry.stokes_bdry_compact.Defs
import Problems.Geometry.stokes_dd_zero.Defs
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_integral.Defs
import Problems.Geometry.stokes_mextderiv.Defs

open scoped Manifold Bundle ContDiff
open Bundle

namespace Problems.Geometry.stokes_closed

end Problems.Geometry.stokes_closed
