/-
  Defs.lean — vocabulary for the multi-chart density transition law
  `localCoeff g x = det(transition') * (localCoeff g x₀ ∘ transition)`.

  No NEW definitions: reuses the Library's `localCoeff` / `topCoeff` / `formInCoord` and the
  proved differential-form chart-transition law `form_in_coord_pullback`. None of these pulls in
  the heavy Stokes proof tower, so init + cold builds stay fast.
-/
import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_integral.Defs
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_pullback

open scoped Manifold Bundle ContDiff
open Bundle

namespace Problems.Geometry.integral_param

end Problems.Geometry.integral_param
